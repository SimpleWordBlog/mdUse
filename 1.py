import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
from pathlib import Path
import re
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime
from queue import Queue
import logging
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

CONFIG_FILE = "summarizer_config.json"

# 阶跃星辰模型列表
STEP_MODELS = [
    "step-1-8k",
    "step-1-32k",
    "step-1-128k",
    "step-1-256k",
    "step-2-16k",
    "step-2-16k-exp",
    "step-1-flash",
    "step-2-mini"
]

class MarkdownSummarizer:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Markdown 摘要生成器")
        self.window.geometry("1024x768")

        # 设置主题
        style = ttk.Style()
        style.theme_use('clam')

        # 自定义样式
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        style.configure('Status.TLabel', font=('Helvetica', 10))

        # 加载配置
        self.config = self.load_config()

        # 初始化变量
        self.failed_files = []
        self.is_processing = False
        self.process_queue = Queue()

        self.setup_ui()
        self.setup_logging()

    def setup_logging(self):
        """设置日志，使用UTF-8编码"""
        logging.basicConfig(
            filename='summarizer.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            encoding='utf-8'
        )

    def create_labeled_entry(self, parent, label_text, default_value="", password=False):
        """创建带标签的输入框"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=5)

        label = ttk.Label(frame, text=label_text, style='Header.TLabel')
        label.pack(side='top', anchor='w')

        if password:
            entry = ttk.Entry(frame, show="*")
        else:
            entry = ttk.Entry(frame)
        entry.insert(0, default_value)
        entry.pack(side='top', fill='x', pady=(2, 0))

        return entry, frame

    def create_labeled_spinbox(self, parent, label_text, default_value, min_value, max_value):
        """创建带标签的数字输入框"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=5)

        label = ttk.Label(frame, text=label_text, style='Header.TLabel')
        label.pack(side='top', anchor='w')

        spinbox = ttk.Spinbox(frame, from_=min_value, to=max_value)
        spinbox.insert(0, default_value)
        spinbox.pack(side='top', fill='x', pady=(2, 0))

        return spinbox, frame

    def create_labeled_combobox(self, parent, label_text, values, default_value=""):
        """创建带标签的下拉选择框"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=5)

        label = ttk.Label(frame, text=label_text, style='Header.TLabel')
        label.pack(side='top', anchor='w')

        combobox = ttk.Combobox(frame, values=values, state="readonly")
        if default_value in values:
            combobox.set(default_value)
        else:
            combobox.current(0)
        combobox.pack(side='top', fill='x', pady=(2, 0))

        return combobox, frame

    def setup_ui(self):
        """设置用户界面"""
        # 主容器
        main_container = ttk.Frame(self.window)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # 标题
        title = ttk.Label(main_container, text="Markdown 摘要生成器", style='Title.TLabel')
        title.pack(pady=(0, 20))

        # 创建选项卡
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill='both', expand=True, padx=5)

        # 配置页面
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text='配置')

        # API设置区域
        settings_frame = ttk.LabelFrame(config_frame, text="API 设置", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=5)

        self.api_key_entry, _ = self.create_labeled_entry(
            settings_frame,
            "API密钥:",
            self.config.get('api_key', os.getenv('STEP_API_KEY', '')),
            password=True
        )

        # 模型选择下拉框
        self.model_combobox, _ = self.create_labeled_combobox(
            settings_frame,
            "模型:",
            STEP_MODELS,
            self.config.get('model', 'step-1-8k')
        )

        # 请求间隔时间设置
        self.request_interval_spinbox, _ = self.create_labeled_spinbox(
            settings_frame,
            "请求间隔时间（秒）:",
            self.config.get('request_interval', 3),
            1,
            10
        )

        # 摘要设置区域
        summary_frame = ttk.LabelFrame(config_frame, text="摘要设置", padding=10)
        summary_frame.pack(fill='x', padx=10, pady=5)

        self.length_entry, _ = self.create_labeled_entry(
            summary_frame,
            "摘要长度（字符数）:",
            str(self.config.get('summary_length', 200))
        )

        # 文件选择区域
        file_frame = ttk.LabelFrame(config_frame, text="文件设置", padding=10)
        file_frame.pack(fill='x', padx=10, pady=5)

        # 单文件选择
        single_file_frame = ttk.Frame(file_frame)
        single_file_frame.pack(fill='x', pady=5)

        ttk.Label(single_file_frame, text="单个文件:", style='Header.TLabel').pack(side='top', anchor='w')

        file_select_frame = ttk.Frame(single_file_frame)
        file_select_frame.pack(fill='x')

        self.file_entry = ttk.Entry(file_select_frame)
        self.file_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

        browse_file_btn = ttk.Button(file_select_frame, text="选择文件", command=self.browse_file)
        browse_file_btn.pack(side='right')

        process_file_btn = ttk.Button(file_select_frame, text="处理文件", command=self.process_single_file)
        process_file_btn.pack(side='right', padx=5)

        # 目录选择
        dir_select_frame = ttk.Frame(file_frame)
        dir_select_frame.pack(fill='x', pady=(10, 0))

        ttk.Label(dir_select_frame, text="批量处理目录:", style='Header.TLabel').pack(side='top', anchor='w')

        dir_input_frame = ttk.Frame(dir_select_frame)
        dir_input_frame.pack(fill='x')

        self.dir_entry = ttk.Entry(dir_input_frame)
        self.dir_entry.insert(0, self.config.get('directory', ''))
        self.dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

        browse_dir_btn = ttk.Button(dir_input_frame, text="选择目录", command=self.browse_directory)
        browse_dir_btn.pack(side='right')

        # 按钮区域
        button_frame = ttk.Frame(config_frame)
        button_frame.pack(fill='x', pady=20)

        save_btn = ttk.Button(button_frame, text="保存配置", command=lambda: self.save_config(show_message=True))
        save_btn.pack(side='left', padx=5)

        self.start_button = ttk.Button(button_frame, text="开始批量处理", command=self.start_processing)
        self.start_button.pack(side='left', padx=5)

        self.retry_button = ttk.Button(
            button_frame,
            text="重试失败",
            command=self.retry_failed,
            state='disabled'
        )
        self.retry_button.pack(side='left', padx=5)

        # 进度页面
        progress_frame = ttk.Frame(notebook)
        notebook.add(progress_frame, text='处理进度')

        # 状态标签
        self.status_label = ttk.Label(
            progress_frame,
            text="就绪",
            style='Status.TLabel'
        )
        self.status_label.pack(pady=5)

        # 进度显示
        self.progress_text = scrolledtext.ScrolledText(
            progress_frame,
            height=20,
            width=70
        )
        self.progress_text.pack(pady=5, padx=5, fill='both', expand=True)

    def browse_file(self):
        """选择单个Markdown文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)

    def process_single_file(self):
        """处理单个文件"""
        # 先保存当前配置
        self.save_config()

        file_path = self.file_entry.get()
        if not file_path:
            messagebox.showerror("错误", "请选择一个Markdown文件")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("错误", "文件不存在")
            return

        self.progress_text.delete(1.0, tk.END)
        self.log_message(f"开始处理文件: {file_path}")

        def process_worker():
            try:
                if self.process_markdown_file(file_path):
                    messagebox.showinfo("成功", "文件处理完成！")
                else:
                    messagebox.showerror("错误", "文件处理失败，请查看日志了解详情")
            except Exception as e:
                messagebox.showerror("错误", f"处理过程出错: {str(e)}")
            finally:
                self.update_status("处理完成")

        threading.Thread(target=process_worker, daemon=True).start()

    def update_status(self, message):
        """更新状态标签"""
        self.status_label.config(text=message)
        self.window.update()

    def log_message(self, message):
        """记录消息到UI和日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.progress_text.insert(tk.END, formatted_message + "\n")
        self.progress_text.see(tk.END)
        logging.info(message)

    def process_markdown_file(self, file_path):
        """处理单个Markdown文件，使用阶跃星辰API"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 移除现有的摘要信息（如果有）
            content = re.sub(r'---\narticleGPT:.*?\n---\n', '', content, flags=re.DOTALL)

            # 使用阶跃星辰API
            client = OpenAI(
                api_key=self.api_key_entry.get(),
                base_url="https://api.stepfun.com/v1"
            )

            # 改进的提示词
            prompt = f"""请为以下markdown内容生成一个简洁、紧凑的摘要，必须遵循以下要求：
1. 字数严格控制在{self.length_entry.get()}字以内
2. 不要使用markdown格式（不要使用标题、列表符号、强调符号等）
3. 使用连贯的、流畅的叙述性文本
4. 只提取文档中最核心、最重要的信息
5. 使用客观、简洁的语言风格
6. 摘要应该是一段完整的文字，不要分段

以下是需要摘要的内容：

{content}"""

            response = client.chat.completions.create(
                model=self.model_combobox.get(),
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的文档摘要生成助手。你的任务是提取文档的核心信息，并生成简洁、紧凑、易读的摘要。不要使用任何markdown格式，只生成纯文本摘要。"
                    },
                    {"role": "user", "content": prompt}
                ]
            )

            summary = response.choices[0].message.content.strip()
            new_content = f"---\narticleGPT: {summary}\nshow: true\n---\n\n{content}"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            self.log_message(f"✅ 成功处理: {file_path}")
            return True

        except Exception as e:
            self.log_message(f"❌ 处理失败 {file_path}: {str(e)}")
            with self.process_queue.mutex:
                self.process_queue.queue.clear()
            self.failed_files.append(file_path)
            return False

    def process_directory(self):
        """处理目录中的所有Markdown文件"""
        try:
            directory = self.dir_entry.get()
            if not directory:
                messagebox.showerror("错误", "请选择一个目录")
                return

            markdown_files = list(Path(directory).rglob("*.md"))
            if not markdown_files:
                messagebox.showinfo("提示", "在选定目录中未找到Markdown文件")
                return

            self.failed_files = []
            total_files = len(markdown_files)
            self.log_message(f"找到 {total_files} 个Markdown文件。开始处理...")
            self.update_status(f"正在处理 {total_files} 个文件...")

            for file_path in markdown_files:
                self.process_queue.put(file_path)

            # 获取请求间隔时间
            request_interval = int(self.request_interval_spinbox.get())

            with ThreadPoolExecutor(max_workers=1) as executor:  # 限制为1个并发请求
                futures = []
                while not self.process_queue.empty():
                    file_path = self.process_queue.get()
                    future = executor.submit(self.process_markdown_file, file_path)
                    futures.append(future)
                    # 添加请求间隔时间
                    time.sleep(request_interval)

                completed = 0
                for future in futures:
                    if future.result():
                        completed += 1
                    self.update_status(f"已完成: {completed}/{total_files}")

            self.log_message(f"\n处理完成！")
            self.log_message(f"成功处理: {completed}")
            self.log_message(f"失败: {len(self.failed_files)}")

            if self.failed_files:
                self.retry_button.config(state='normal')

        except Exception as e:
            self.log_message(f"处理过程出错: {str(e)}")
        finally:
            self.is_processing = False
            self.start_button.config(state='normal')
            self.update_status("处理完成")

    def retry_failed(self):
        """重试失败的文件"""
        if not self.failed_files:
            return

        self.retry_button.config(state='disabled')
        self.log_message("\n重试失败的文件...")

        failed_files = self.failed_files.copy()
        self.failed_files = []
        total_files = len(failed_files)

        # 获取请求间隔时间
        request_interval = int(self.request_interval_spinbox.get())

        for file_path in failed_files:
            self.process_queue.put(file_path)

        def retry_worker():
            completed = 0
            while not self.process_queue.empty():
                file_path = self.process_queue.get()
                if self.process_markdown_file(file_path):
                    completed += 1
                self.update_status(f"重试进度: {completed}/{total_files}")
                # 添加请求间隔时间
                time.sleep(request_interval)

            self.log_message(f"\n重试完成！")
            self.log_message(f"成功处理: {completed}")
            self.log_message(f"失败: {len(self.failed_files)}")

            if not self.failed_files:
                self.retry_button.config(state='disabled')
            else:
                self.retry_button.config(state='normal')

            self.update_status("重试完成")

        threading.Thread(target=retry_worker, daemon=True).start()

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_config(self, show_message=False):
        """保存配置
        Args:
            show_message (bool): 是否显示保存成功的提示框
        """
        config = {
            'api_key': self.api_key_entry.get(),
            'model': self.model_combobox.get(),
            'summary_length': int(self.length_entry.get()),
            'directory': self.dir_entry.get(),
            'request_interval': int(self.request_interval_spinbox.get())
        }

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        if show_message:
            messagebox.showinfo("成功", "配置保存成功！")

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)

    def start_processing(self):
        if self.is_processing:
            return

        # 先保存当前配置
        self.save_config()

        self.is_processing = True
        self.start_button.config(state='disabled')
        self.retry_button.config(state='disabled')
        self.progress_text.delete(1.0, tk.END)

        threading.Thread(target=self.process_directory, daemon=True).start()

    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    app = MarkdownSummarizer()
    app.run()