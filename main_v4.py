import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pyperclip
import keyboard
from pynput import mouse
import threading
from ollama import Client
from openai import OpenAI  # 导入 OpenAI SDK
import time
import subprocess
import os

class ControlPanel(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("控制面板")
        self.geometry("300x350")
        self.app = app

        menubar = tk.Menu(self)

        self.model_menu = tk.Menu(menubar, tearoff=0)
        # 仅在 Ollama 模式下可用的模型
        self.ollama_models = ["deepseek-r1:7b", "llama3.2:3b", "deepseek-r1:1.5b", "deepseek-r1:32b", "mistral:7b"]
        for model in self.ollama_models:
            self.model_menu.add_command(label=model,
                                        command=lambda m=model: self.set_model(m))
        # 仅在 DeepSeek API 模式下可用的模型
        self.api_models = ["deepseek-chat", "deepseek-reasoner"]
        for model in self.api_models:
            self.model_menu.add_command(label=model,
                                        command=lambda m=model: self.set_model(m))
        menubar.add_cascade(label="模型选择", menu=self.model_menu)

        self.api_mode_menu = tk.Menu(menubar, tearoff=0)
        self.api_mode_menu.add_command(label="Ollama 模式",
                                       command=lambda: self.set_api_mode(False))
        self.api_mode_menu.add_command(label="DeepSeek API 模式",
                                       command=lambda: self.set_api_mode(True))
        menubar.add_cascade(label="API 模式选择", menu=self.api_mode_menu)

        self.config(menu=menubar)

        self.set_api_btn = ttk.Button(self, text="设置 DeepSeek API",
                                      command=self.set_deepseek_api)
        self.set_api_btn.pack(pady=10)

        self.set_api_url_btn = ttk.Button(self, text="设置 DeepSeek API 请求地址",
                                          command=self.set_deepseek_api_url)
        self.set_api_url_btn.pack(pady=10)

        # 添加 prompt 设置功能
        self.set_prompt_btn = ttk.Button(self, text="设置 Prompt",
                                         command=self.set_prompt)
        self.set_prompt_btn.pack(pady=10)

        self.auto_translate_enabled = False
        self.status_var = tk.StringVar(value="状态：已停止")

        self.toggle_btn = ttk.Button(self, text="开始自动翻译",
                                     command=self.toggle_auto_translate)
        self.toggle_btn.pack(pady=10)

        self.status_label = ttk.Label(self, textvariable=self.status_var)
        self.status_label.pack()

        # 显示当前模型的标签
        self.current_model_label = ttk.Label(self, text=f"当前模型: {self.app.current_model}")
        self.current_model_label.pack(pady=5)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 获取 main_v4.py 所在目录
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        # 组合 profile.txt 的完整路径
        self.profile_path = os.path.join(self.script_dir, "profile.txt")

        # 从 profile.txt 中读取配置信息
        self.read_profile()

        # 初始化模型选择菜单状态
        self.update_model_menu_state()

    def read_profile(self):
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if len(lines) >= 1:
                    self.deepseek_api_key = lines[0].strip()
                if len(lines) >= 2:
                    self.deepseek_api_url = lines[1].strip()
                if len(lines) >= 3:
                    self.prompt = lines[2].strip()
        except FileNotFoundError:
            # 如果文件不存在，使用默认值
            self.deepseek_api_key = ""
            self.deepseek_api_url = "https://api.deepseek.com"  # 默认请求地址
            self.prompt = "翻译以下内容（中英互译）"  # 默认 prompt

        self.use_deepseek_api = False

    def write_profile(self):
        lines = []
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            pass

        # 清空前三行
        if len(lines) >= 1:
            lines[0] = f"{self.deepseek_api_key}\n"
        else:
            lines.append(f"{self.deepseek_api_key}\n")
        if len(lines) >= 2:
            lines[1] = f"{self.deepseek_api_url}\n"
        else:
            lines.append(f"{self.deepseek_api_url}\n")
        if len(lines) >= 3:
            lines[2] = f"{self.prompt}\n"
        else:
            lines.append(f"{self.prompt}\n")

        with open(self.profile_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # 输出 profile.txt 的目录
        file_dir = os.path.dirname(self.profile_path)
        print(f"profile.txt 所在目录: {file_dir}")

        # 添加调试代码，逐行输出 profile.txt 的内容
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                print("profile.txt 的内容如下：")
                for line in f:
                    print(line.strip())
        except FileNotFoundError:
            print("文件 profile.txt 未找到")

    def set_model(self, model_name):
        if (self.use_deepseek_api and model_name in self.api_models) or \
                (not self.use_deepseek_api and model_name in self.ollama_models):
            # 如果在 Ollama 模式下且模型不存在，尝试下载
            if not self.use_deepseek_api and not self.model_exists(model_name):
                if messagebox.askyesno("模型不存在", f"模型 {model_name} 不存在，是否下载？"):
                    if self.download_ollama_model(model_name):
                        self.app.current_model = model_name  # 修改主应用的当前模型
                        self.current_model_label.config(text=f"当前模型: {model_name}")  # 更新当前模型标签
                        messagebox.showinfo("模型切换", f"已切换到模型：{model_name}")
                    else:
                        messagebox.showerror("下载失败", f"模型 {model_name} 下载失败，请检查网络或重试。")
                        return
                else:
                    return
            else:
                self.app.current_model = model_name  # 修改主应用的当前模型
                self.current_model_label.config(text=f"当前模型: {model_name}")  # 更新当前模型标签
                messagebox.showinfo("模型切换", f"已切换到模型：{model_name}")
        else:
            messagebox.showerror("错误", f"该模型在当前模式下不可用，请切换 API 模式。")

    def set_api_mode(self, use_api):
        self.use_deepseek_api = use_api
        if use_api:
            messagebox.showinfo("API 模式切换", "已切换到 DeepSeek API 模式")
            # 切换到 DeepSeek API 模式时，默认选择第一个 DeepSeek API 模型
            if self.api_models:
                self.set_model(self.api_models[0])
        else:
            messagebox.showinfo("API 模式切换", "已切换到 Ollama 模式")
            # 切换到 Ollama 模式时，默认选择第一个 Ollama 模型
            if self.ollama_models:
                self.set_model(self.ollama_models[0])
        self.update_model_menu_state()

    def set_deepseek_api(self):
        api_key = simpledialog.askstring("设置 DeepSeek API", "请输入 DeepSeek API 密钥：",initialvalue=self.deepseek_api_key)
        if api_key:
            self.deepseek_api_key = api_key
            # 更新 profile.txt 文件
            self.write_profile()
            messagebox.showinfo("API 密钥设置", "DeepSeek API 密钥已设置")

    def set_deepseek_api_url(self):
        api_url = simpledialog.askstring("设置 DeepSeek API 请求地址", "请输入 DeepSeek API 请求地址：",initialvalue=self.deepseek_api_url)
        if api_url:
            self.deepseek_api_url = api_url
            # 更新 profile.txt 文件
            self.write_profile()
            messagebox.showinfo("API 请求地址设置", "DeepSeek API 请求地址已设置")

    def set_prompt(self):
        prompt = simpledialog.askstring("设置 Prompt", "请输入 Prompt：",initialvalue=self.prompt)
        if prompt:
            self.prompt = prompt
            # 更新 profile.txt 文件
            self.write_profile()
            messagebox.showinfo("Prompt 设置", "Prompt 已设置")

    def toggle_auto_translate(self):
        self.auto_translate_enabled = not self.auto_translate_enabled
        if self.auto_translate_enabled:
            self.toggle_btn.config(text="停止自动翻译")
            self.status_var.set("状态：正在运行")
            # 点击自动翻译后立即显示窗口
            self.app.floating_window.deiconify()
        else:
            self.toggle_btn.config(text="开始自动翻译")
            self.status_var.set("状态：已停止")

    def on_close(self):
        self.withdraw()

    def update_model_menu_state(self):
        for i, model in enumerate(self.ollama_models):
            self.model_menu.entryconfig(i, state=tk.NORMAL if not self.use_deepseek_api else tk.DISABLED)
        for i, model in enumerate(self.api_models):
            self.model_menu.entryconfig(i + len(self.ollama_models), state=tk.NORMAL if self.use_deepseek_api else tk.DISABLED)

    def model_exists(self, model_name):
        try:
            # 这里可以添加实际检查模型是否存在的逻辑，例如调用 ollama 相关接口
            # 暂时简单返回 True，你需要根据实际情况实现
            return True
        except Exception as e:
            print(f"检查模型 {model_name} 存在性时出错: {e}")
            return False

    def download_ollama_model(self, model_name):
        try:
            # 调用命令行执行 ollama pull 命令
            subprocess.run(["ollama", "pull", model_name], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"下载模型 {model_name} 时出错: {e}")
            return False


class FloatingWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(False)  # 允许窗口有标题栏以便拖动改变大小
        self.attributes("-alpha", 0.95)
        self.attributes("-topmost", True)

        self.text = tk.Text(self, wrap=tk.WORD,
                            width=40, height=10,
                            font=("Arial", 10),
                            padx=5, pady=5)
        self.text.pack(fill=tk.BOTH, expand=True)

        # 创建菜单用于修改文字大小
        menubar = tk.Menu(self)
        font_menu = tk.Menu(menubar, tearoff=0)
        font_sizes = [8, 10, 12, 14, 16, 18, 20]
        for size in font_sizes:
            font_menu.add_command(label=f"字体大小: {size}", command=lambda s=size: self.change_font_size(s))
        menubar.add_cascade(label="字体", menu=font_menu)
        self.config(menu=menubar)

        #close_btn = ttk.Button(self, text="×",
                               #command=self.hide_window,
                               #width=3)
        #close_btn.place(relx=1, x=-30, y=5, anchor=tk.NE)

        self.withdraw()

    def hide_window(self):
        self.withdraw()

    def show_translation(self, text):
        self.deiconify()
        self.text.delete(1.0, tk.END)
        self.text.insert(tk.END, text)

    def change_font_size(self, size):
        self.text.config(font=("Arial", size))


class TranslationApp:
    def __init__(self, root):
        pyperclip.copy('')  # 清空剪贴板
        self.root = root
        root.title("划词翻译")
        root.geometry("300x200")

        self.current_model = 'deepseek-r1:7b'  # 初始化当前模型
        # 先初始化其他属性，再初始化 ControlPanel
        self.floating_window = FloatingWindow(root)
        self.ollama = Client(host='http://localhost:11434')

        self.setup_hotkey()
        self.running = True
        self.last_selection = ""

        self.control_panel = ControlPanel(root, self)  # 传递 self 给 ControlPanel

        self.mouse_controller = mouse.Controller()
        self.mouse_press_time = 0
        self.listener = mouse.Listener(on_click=self.on_mouse_click)
        self.listener.start()

    def on_mouse_click(self, x, y, button, pressed):
        if pressed:
            self.mouse_press_time = time.time()
        else:
            release_time = time.time()
            duration = release_time - self.mouse_press_time
            if duration >= 0.5:  # 按下时间超过0.5秒才处理
                threading.Timer(0.1, self.delayed_clipboard_read).start()

    def delayed_clipboard_read(self):
        selected = self.get_selected_text()
        if selected and selected != self.last_selection:
            self.last_selection = selected
            translation = self.translate_text(selected)
            self.floating_window.show_translation(f"原文：{selected}\n\n翻译：{translation}")

    def setup_hotkey(self):
        keyboard.add_hotkey('ctrl+alt+t', self.trigger_translation)

    def get_selected_text(self):
        try:
            original = pyperclip.paste()
            keyboard.send('ctrl+c')
            time.sleep(0.1)
            selected = pyperclip.paste()
            pyperclip.copy(original)
            return selected.strip()
        except Exception as e:
            print("获取选中文本出错:", e)
            return ""

    def translate_text(self, text):
        if self.control_panel.use_deepseek_api:
            if not self.control_panel.deepseek_api_key:
                return "请先设置 DeepSeek API 密钥"
            try:
                client = OpenAI(
                    api_key=self.control_panel.deepseek_api_key,
                    base_url=self.control_panel.deepseek_api_url
                )
                response = client.chat.completions.create(
                    model=self.current_model,
                    messages=[
                        {"role": "system", "content": self.control_panel.prompt},
                        {"role": "user", "content": text}
                    ],
                    stream=False
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"翻译失败: {str(e)}"
        else:
            try:
                response = self.ollama.generate(
                    model=self.current_model,
                    prompt=f"{self.control_panel.prompt}：\n{text}",
                    stream=False
                )
                raw_output = response['response']
                clean_output = raw_output.replace("</think>", "").replace("<think>", "").strip()
                return clean_output
            except Exception as e:
                return f"翻译失败: {str(e)}"

    def trigger_translation(self):
        if not self.control_panel.auto_translate_enabled:
            selected = self.get_selected_text()
            if selected:
                translation = self.translate_text(selected)
                self.floating_window.show_translation(
                    f"原文：{selected}\n\n翻译：{translation}"
                )

    def on_closing(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = TranslationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()