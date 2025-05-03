import os
import json
import re
import time
import logging
import threading
import concurrent.futures
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 全局配置
CONFIG_FILE = "summarizer_config.json"
LOG_FILE = "summarizer.log"

# 设置主题
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class AIModel:
    """统一的AI模型类，适用于所有API类型"""
    def __init__(self, name, base_url, api_key_name=None, models=None, model_type="generic"):
        self.name = name
        self.base_url = base_url
        self.api_key_name = api_key_name or f"{name.upper()}_API_KEY"
        self.api_key = os.getenv(self.api_key_name, "")
        self.models = models or []
        self.selected_model = self.models[0] if self.models else ""
        self.model_type = model_type  # "openai", "anthropic", "gemini"
        
    def generate_summary(self, content, max_length, prompt_template, api_key=None):
        """根据模型类型生成摘要"""
        api_key = api_key or self.api_key
        
        # 格式化提示模板
        prompt = prompt_template.format(max_length=max_length, content=content)
        
        if self.model_type == "openai":
            # OpenAI兼容API
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=self.base_url)
            
            response = client.chat.completions.create(
                model=self.selected_model,
                messages=[
                    {"role": "system", "content": "你是专业的文档摘要助手。提取核心信息并生成简洁、紧凑、可读的摘要。不要使用markdown格式，只生成纯文本摘要。"},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
            
        elif self.model_type == "anthropic":
            # Anthropic API
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            
            response = client.messages.create(
                model=self.selected_model,
                max_tokens=1024,
                system="你是专业的文档摘要助手。提取核心信息并生成简洁、紧凑、可读的摘要。不要使用markdown格式，只生成纯文本摘要。",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
            
        elif self.model_type == "gemini":
            # Google Gemini API
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            model = genai.GenerativeModel(self.selected_model)
            response = model.generate_content(prompt)
            
            return response.text.strip()
        
        return "错误：不支持的模型类型"

    def to_dict(self):
        """转换为字典以保存配置"""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "api_key_name": self.api_key_name,
            "api_key": self.api_key,
            "models": self.models,
            "selected_model": self.selected_model,
            "model_type": self.model_type
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建实例"""
        instance = cls(
            data["name"],
            data["base_url"],
            data["api_key_name"],
            data.get("models", []),
            data.get("model_type", "generic")
        )
        instance.api_key = data.get("api_key", "")
        instance.selected_model = data.get("selected_model", instance.selected_model)
        return instance

class CenteredWindow(ctk.CTkToplevel):
    """居中窗口基类"""
    def __init__(self, parent, title, size):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{size[0]}x{size[1]}")
        self.grab_set()  # 模态对话框
        
        # 使窗口居中
        self.center_window()
        
    def center_window(self):
        """使窗口在屏幕中居中"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')

class ModelAddDialog(CenteredWindow):
    """添加新模型对话框"""
    def __init__(self, parent):
        super().__init__(parent, "添加新模型", (500, 400))
        
        self.result = None
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        # 标题
        title = ctk.CTkLabel(self, text="添加新的AI模型", font=("黑体", 16, "bold"))
        title.pack(pady=(20, 20))
        
        # 模型名称
        name_frame = ctk.CTkFrame(self)
        name_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(name_frame, text="模型名称：").pack(side="left", padx=5)
        
        self.name_entry = ctk.CTkEntry(name_frame)
        self.name_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 模型类型
        type_frame = ctk.CTkFrame(self)
        type_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(type_frame, text="模型类型：").pack(side="left", padx=5)
        
        self.type_var = ctk.StringVar(value="openai")
        type_dropdown = ctk.CTkComboBox(
            type_frame,
            values=["openai", "anthropic", "gemini"],
            variable=self.type_var
        )
        type_dropdown.pack(side="left", fill="x", expand=True, padx=5)
        
        # API Base URL
        base_url_frame = ctk.CTkFrame(self)
        base_url_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(base_url_frame, text="API基础URL：").pack(side="left", padx=5)
        
        self.base_url_entry = ctk.CTkEntry(base_url_frame)
        self.base_url_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # API密钥
        api_key_frame = ctk.CTkFrame(self)
        api_key_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(api_key_frame, text="API密钥：").pack(side="left", padx=5)
        
        self.api_key_entry = ctk.CTkEntry(api_key_frame, show="*")
        self.api_key_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 模型ID
        model_id_frame = ctk.CTkFrame(self)
        model_id_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(model_id_frame, text="模型ID：").pack(side="left", padx=5)
        
        self.model_id_entry = ctk.CTkEntry(model_id_frame)
        self.model_id_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 按钮
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(button_frame, text="取消", command=self.cancel).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="确认", command=self.confirm).pack(side="right", padx=10)
    
    def cancel(self):
        """取消添加"""
        self.result = None
        self.destroy()
    
    def confirm(self):
        """确认添加"""
        model_name = self.name_entry.get().strip()
        base_url = self.base_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        model_id = self.model_id_entry.get().strip()
        model_type = self.type_var.get()
        
        if not model_name:
            messagebox.showerror("错误", "模型名称不能为空")
            return
        
        if not base_url and model_type != "gemini":
            messagebox.showerror("错误", "API基础URL不能为空")
            return
        
        if not model_id:
            messagebox.showerror("错误", "模型ID不能为空")
            return
        
        # 创建结果
        self.result = {
            "name": model_name,
            "base_url": base_url,
            "api_key": api_key,
            "model_id": model_id,
            "model_type": model_type
        }
        
        self.destroy()

class PromptEditDialog(CenteredWindow):
    """编辑提示模板对话框"""
    def __init__(self, parent, current_template):
        super().__init__(parent, "编辑提示模板", (600, 500))
        
        self.template = current_template
        self.result = None
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        # 标题
        title = ctk.CTkLabel(self, text="编辑摘要提示模板", font=("黑体", 16, "bold"))
        title.pack(pady=(20, 20))
        
        # 帮助文本
        help_text = ctk.CTkLabel(self, text="使用{max_length}表示摘要长度，{content}表示Markdown内容")
        help_text.pack(pady=(0, 10))
        
        # 提示模板文本区域
        self.template_text = ctk.CTkTextbox(self, height=300)
        self.template_text.pack(fill="both", expand=True, padx=20, pady=10)
        self.template_text.insert("1.0", self.template)
        
        # 按钮
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(button_frame, text="取消", command=self.cancel).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="保存", command=self.save).pack(side="right", padx=10)
    
    def cancel(self):
        """取消编辑"""
        self.result = None
        self.destroy()
    
    def save(self):
        """保存编辑的模板"""
        template = self.template_text.get("1.0", "end-1c")
        
        if not template:
            messagebox.showerror("错误", "模板不能为空")
            return
        
        if "{content}" not in template:
            messagebox.showerror("错误", "模板必须包含{content}占位符")
            return
        
        if "{max_length}" not in template:
            messagebox.showerror("错误", "模板必须包含{max_length}占位符")
            return
        
        self.result = template
        self.destroy()

class MarkdownSummarizer:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title("Markdown 摘要生成器")
        # 设置初始大小，先不要在这里调用 center_window
        self.window.geometry("1024x768")
        # 初始化变量
        self.failed_files = []
        self.is_processing = False
        self.max_workers = 5  # 并发工作线程数
        # 默认提示模板
        self.default_prompt_template = """请为以下Markdown内容创建一个简洁、紧凑的摘要，严格遵循以下要求：
1. 保持在{max_length}个字符以内，务必简洁
2. 不要使用Markdown语法或格式（不要标题、列表符号、强调、应用、代码块、''等）
3. 使用连贯、流畅的叙述文本
4. 只提取文档最核心、最重要的信息
5. 使用客观、简洁的语言风格
6. 摘要应该是完整的文本，没有段落、空格或换行，总是紧凑到上一个内容位置
以下是要总结的内容：
{content}"""
        # 加载配置
        self.load_config()
        # 设置日志
        self.setup_logging()
        # 设置UI
        self.setup_ui()
        self.window.after(100, self.center_window)
    
    def center_window(self):
        """使主窗口在屏幕中居中"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'+{x}+{y}')
    
    def setup_logging(self):
        """设置带有UTF-8编码的日志"""
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            encoding='utf-8'
        )
    
    def load_config(self):
        """加载配置"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载摘要设置
                self.summary_length = config.get("summary_length", 200)
                self.directory = config.get("directory", "")
                self.request_interval = config.get("request_interval", 3)
                self.max_workers = config.get("max_workers", 5)
                self.prompt_template = config.get("prompt_template", self.default_prompt_template)
                
                # 加载模型
                self.models = {}
                self.active_model = None
                
                models_data = config.get("models", {})
                for name, model_data in models_data.items():
                    self.models[name] = AIModel.from_dict(model_data)
                
                # 设置活动模型
                self.active_model = config.get("active_model")
                if not self.active_model or self.active_model not in self.models:
                    if self.models:
                        self.active_model = list(self.models.keys())[0]
                    else:
                        # 如果没有模型，添加默认模型
                        default_model = AIModel(
                            "深度求索",
                            "https://api.deepseek.com",
                            "DEEPSEEK_API_KEY",
                            ["deepseek-chat"],
                            "openai"
                        )
                        self.models[default_model.name] = default_model
                        self.active_model = default_model.name
                
        except FileNotFoundError:
            # 创建默认配置
            self.summary_length = 200
            self.directory = ""
            self.request_interval = 3
            self.max_workers = 5
            self.prompt_template = self.default_prompt_template
            
            # 添加默认模型
            default_model = AIModel(
                "深度求索", 
                "https://api.deepseek.com", 
                "DEEPSEEK_API_KEY",
                ["deepseek-chat"],
                "openai"
            )
            self.models = {default_model.name: default_model}
            self.active_model = default_model.name
    
    def save_config(self):
        """保存配置"""
        config = {
            "summary_length": self.summary_length,
            "directory": self.directory,
            "request_interval": self.request_interval,
            "max_workers": self.max_workers,
            "prompt_template": self.prompt_template,
            "models": {name: model.to_dict() for name, model in self.models.items()},
            "active_model": self.active_model
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return True
    
    def setup_ui(self):
        """设置用户界面"""
        # 主容器
        self.main_container = ctk.CTkFrame(self.window)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 标题
        title = ctk.CTkLabel(
            self.main_container, 
            text="Markdown 摘要生成器", 
            font=("黑体", 24, "bold")
        )
        title.pack(pady=(10, 20))
        
        # 创建选项卡控件
        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 创建选项卡
        self.config_tab = self.tabview.add("配置")
        self.model_tab = self.tabview.add("模型")
        self.processing_tab = self.tabview.add("进度")
        
        # 设置配置选项卡
        self.setup_config_tab()
        
        # 设置模型选项卡
        self.setup_model_tab()
        
        # 设置处理进度选项卡
        self.setup_processing_tab()
    
    def setup_config_tab(self):
        """设置配置选项卡"""
        # 摘要设置
        summary_frame = ctk.CTkFrame(self.config_tab)
        summary_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(summary_frame, text="摘要设置", font=("黑体", 16, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # 摘要长度
        length_frame = ctk.CTkFrame(summary_frame)
        length_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(length_frame, text="摘要长度（字符）：").pack(side="left", padx=5)
        
        self.length_var = ctk.StringVar(value=str(self.summary_length))
        length_entry = ctk.CTkEntry(length_frame, textvariable=self.length_var)
        length_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 请求间隔
        interval_frame = ctk.CTkFrame(summary_frame)
        interval_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(interval_frame, text="请求间隔（秒）：").pack(side="left", padx=5)
        
        self.interval_var = ctk.StringVar(value=str(self.request_interval))
        interval_spinbox = ctk.CTkOptionMenu(
            interval_frame, 
            values=[str(i) for i in range(1, 11)],
            variable=self.interval_var
        )
        interval_spinbox.pack(side="left", padx=5)
        
        # 并发数
        concurrency_frame = ctk.CTkFrame(summary_frame)
        concurrency_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(concurrency_frame, text="并发工作线程：").pack(side="left", padx=5)
        
        self.workers_var = ctk.StringVar(value=str(self.max_workers))
        workers_spinbox = ctk.CTkOptionMenu(
            concurrency_frame, 
            values=[str(i) for i in range(1, 11)],
            variable=self.workers_var
        )
        workers_spinbox.pack(side="left", padx=5)
        
        # 提示模板编辑按钮
        prompt_frame = ctk.CTkFrame(summary_frame)
        prompt_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(prompt_frame, text="摘要提示：").pack(side="left", padx=5)
        
        edit_prompt_btn = ctk.CTkButton(
            prompt_frame,
            text="编辑提示模板",
            command=self.edit_prompt_template
        )
        edit_prompt_btn.pack(side="left", padx=5)
        
        # 单文件处理
        file_frame = ctk.CTkFrame(self.config_tab)
        file_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(file_frame, text="单文件处理", font=("黑体", 16, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # 文件选择
        file_select_frame = ctk.CTkFrame(file_frame)
        file_select_frame.pack(fill="x", padx=10, pady=5)
        
        self.file_var = ctk.StringVar()
        file_entry = ctk.CTkEntry(file_select_frame, textvariable=self.file_var)
        file_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        browse_file_btn = ctk.CTkButton(
            file_select_frame, 
            text="选择文件", 
            command=self.browse_file
        )
        browse_file_btn.pack(side="left", padx=5)
        
        process_file_btn = ctk.CTkButton(
            file_select_frame, 
            text="处理文件", 
            command=self.process_single_file
        )
        process_file_btn.pack(side="left", padx=5)
        
        # 批量处理
        batch_frame = ctk.CTkFrame(self.config_tab)
        batch_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(batch_frame, text="批量处理", font=("黑体", 16, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # 目录选择
        dir_select_frame = ctk.CTkFrame(batch_frame)
        dir_select_frame.pack(fill="x", padx=10, pady=5)
        
        self.dir_var = ctk.StringVar(value=self.directory)
        dir_entry = ctk.CTkEntry(dir_select_frame, textvariable=self.dir_var)
        dir_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        browse_dir_btn = ctk.CTkButton(
            dir_select_frame, 
            text="选择目录", 
            command=self.browse_directory
        )
        browse_dir_btn.pack(side="left", padx=5)
        
        # 按钮区域
        button_frame = ctk.CTkFrame(self.config_tab)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        save_btn = ctk.CTkButton(
            button_frame, 
            text="保存配置", 
            command=self.save_config_with_message
        )
        save_btn.pack(side="left", padx=10)
        
        self.start_button = ctk.CTkButton(
            button_frame, 
            text="开始批量处理", 
            command=self.start_processing
        )
        self.start_button.pack(side="left", padx=10)
        
        self.retry_button = ctk.CTkButton(
            button_frame, 
            text="重试失败", 
            command=self.retry_failed,
            state="disabled"
        )
        self.retry_button.pack(side="left", padx=10)
    
    def setup_model_tab(self):
        """设置模型选项卡"""
        # 模型选择
        model_select_frame = ctk.CTkFrame(self.model_tab)
        model_select_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(model_select_frame, text="当前活动模型：").pack(side="left", padx=5)
        
        self.active_model_var = ctk.StringVar(value=self.active_model)
        self.active_model_dropdown = ctk.CTkComboBox(
            model_select_frame, 
            values=list(self.models.keys()),
            variable=self.active_model_var,
            command=self.on_active_model_changed
        )
        self.active_model_dropdown.pack(side="left", fill="x", expand=True, padx=5)
        
        # 添加新模型按钮
        add_button = ctk.CTkButton(model_select_frame, text="添加模型", command=self.add_new_model)
        add_button.pack(side="right", padx=5)
        
        # 模型列表框架
        self.models_frame = ctk.CTkScrollableFrame(self.model_tab)
        self.models_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # 刷新模型UI
        self.refresh_models_ui()
    
    def setup_processing_tab(self):
        """设置处理进度选项卡"""
        # 状态标签
        self.status_label = ctk.CTkLabel(
            self.processing_tab,
            text="就绪",
            font=("黑体", 14)
        )
        self.status_label.pack(pady=10)
        
        # 进度条
        self.progress_bar = ctk.CTkProgressBar(self.processing_tab, orientation="horizontal")
        self.progress_bar.pack(fill="x", padx=20, pady=10)
        self.progress_bar.set(0)
        
        # 日志文本区域
        self.log_frame = ctk.CTkFrame(self.processing_tab)
        self.log_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.log_text = ctk.CTkTextbox(self.log_frame, height=400)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
    
    def refresh_models_ui(self):
        """刷新模型配置UI"""
        # 清除当前UI
        for widget in self.models_frame.winfo_children():
            widget.destroy()
        
        # 更新活动模型下拉菜单
        self.active_model_dropdown.configure(values=list(self.models.keys()))
        self.active_model_var.set(self.active_model)
        
        # 为每个模型创建配置区域
        for name, model in self.models.items():
            # 创建模型框架
            model_frame = ctk.CTkFrame(self.models_frame)
            model_frame.pack(fill="x", pady=10, padx=5)
            
            # 模型标题和删除按钮
            header_frame = ctk.CTkFrame(model_frame)
            header_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(header_frame, text=f"{name} ({model.model_type})", font=("黑体", 14, "bold")).pack(side="left", padx=10)
            
            if len(self.models) > 1:  # 至少保留一个模型
                delete_btn = ctk.CTkButton(
                    header_frame, 
                    text="删除", 
                    width=60,
                    fg_color="red", 
                    hover_color="darkred",
                    command=lambda m=name: self.delete_model(m)
                )
                delete_btn.pack(side="right", padx=10)
            
            # API密钥
            key_frame = ctk.CTkFrame(model_frame)
            key_frame.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(key_frame, text="API密钥：").pack(side="left", padx=5)
            
            api_key_entry = ctk.CTkEntry(key_frame, width=300, show="*")
            api_key_entry.insert(0, model.api_key)
            api_key_entry.pack(side="left", fill="x", expand=True, padx=5)
            
            # API密钥保存按钮
            save_key_btn = ctk.CTkButton(
                key_frame,
                text="保存",
                width=60,
                command=lambda m=name, entry=api_key_entry: self.save_api_key(m, entry.get())
            )
            save_key_btn.pack(side="right", padx=5)
            
            # 模型选择（如果有多个模型）
            if model.models:
                model_select_frame = ctk.CTkFrame(model_frame)
                model_select_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(model_select_frame, text="模型：").pack(side="left", padx=5)
                
                model_var = ctk.StringVar(value=model.selected_model)
                model_combobox = ctk.CTkComboBox(
                    model_select_frame, 
                    values=model.models,
                    variable=model_var,
                    command=lambda value, m=name: self.on_model_selection_changed(m, value)
                )
                model_combobox.pack(side="left", fill="x", expand=True, padx=5)
            
            # API基础URL（如果不是Gemini）
            if model.model_type != "gemini":
                url_frame = ctk.CTkFrame(model_frame)
                url_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(url_frame, text="API基础URL：").pack(side="left", padx=5)
                
                url_entry = ctk.CTkEntry(url_frame, width=300)
                url_entry.insert(0, model.base_url)
                url_entry.pack(side="left", fill="x", expand=True, padx=5)
                
                # URL保存按钮
                save_url_btn = ctk.CTkButton(
                    url_frame,
                    text="保存",
                    width=60,
                    command=lambda m=name, entry=url_entry: self.save_base_url(m, entry.get())
                )
                save_url_btn.pack(side="right", padx=5)
    
    def on_active_model_changed(self, value):
        """活动模型更改时"""
        self.active_model = value
        self.save_config()
    
    def on_model_selection_changed(self, model_name, value):
        """模型选择更改时"""
        if model_name in self.models:
            self.models[model_name].selected_model = value
            self.save_config()
    
    def save_api_key(self, model_name, api_key):
        """保存模型的API密钥"""
        if model_name in self.models:
            self.models[model_name].api_key = api_key
            self.save_config()
            messagebox.showinfo("成功", f"{model_name}的API密钥已保存")
    
    def save_base_url(self, model_name, base_url):
        """保存模型的基础URL"""
        if model_name in self.models:
            self.models[model_name].base_url = base_url
            self.save_config()
            messagebox.showinfo("成功", f"{model_name}的基础URL已保存")
    
    def add_new_model(self):
        """添加新模型"""
        dialog = ModelAddDialog(self.window)
        self.window.wait_window(dialog)
        
        if dialog.result:
            model_name = dialog.result["name"]
            base_url = dialog.result["base_url"]
            api_key = dialog.result["api_key"]
            model_id = dialog.result["model_id"]
            model_type = dialog.result["model_type"]
            
            # 确保名称唯一
            if model_name in self.models:
                messagebox.showerror("错误", f"模型名称'{model_name}'已存在")
                return
            
            # 创建新模型
            model = AIModel(
                model_name,
                base_url,
                f"{model_name.upper()}_API_KEY",
                [model_id],
                model_type
            )
            
            # 设置API密钥
            model.api_key = api_key
            
            # 添加新模型
            self.models[model_name] = model
            self.active_model = model_name
            self.refresh_models_ui()
            self.save_config()
    
    def delete_model(self, model_name):
        """删除模型"""
        if len(self.models) <= 1:
            messagebox.showerror("错误", "至少需要保留一个模型配置")
            return
        
        result = messagebox.askyesno("确认", f"确定要删除模型'{model_name}'吗？")
        if result:
            if model_name == self.active_model:
                # 如果删除活动模型，切换到第一个可用模型
                available_models = [m for m in self.models.keys() if m != model_name]
                if available_models:
                    self.active_model = available_models[0]
            
            # 删除模型
            if model_name in self.models:
                del self.models[model_name]
                self.refresh_models_ui()
                self.save_config()
    
    def edit_prompt_template(self):
        """编辑提示模板"""
        dialog = PromptEditDialog(self.window, self.prompt_template)
        self.window.wait_window(dialog)
        
        if dialog.result:
            self.prompt_template = dialog.result
            self.save_config()
            messagebox.showinfo("成功", "提示模板已更新")
    
    def save_config_with_message(self):
        """保存配置并显示消息"""
        # 更新配置值
        self.summary_length = int(self.length_var.get())
        self.request_interval = int(self.interval_var.get())
        self.max_workers = int(self.workers_var.get())
        self.directory = self.dir_var.get()
        
        if self.save_config():
            messagebox.showinfo("成功", "配置已保存")
    
    def browse_file(self):
        """浏览选择Markdown文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Markdown文件", "*.md"), ("所有文件", "*.*")]
        )
        if file_path:
            self.file_var.set(file_path)
    
    def browse_directory(self):
        """浏览选择目录"""
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)
            self.directory = directory
    
    def log_message(self, message):
        """记录消息到UI和日志文件"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 添加到UI
        self.log_text.insert("end", formatted_message + "\n")
        self.log_text.see("end")
        
        # 记录到文件
        logging.info(message)
    
    def update_status(self, message, progress=None):
        """更新状态消息和进度条"""
        self.status_label.configure(text=message)
        
        if progress is not None:
            self.progress_bar.set(progress)
        
        self.window.update_idletasks()
    
    def process_single_file(self):
        """处理单个Markdown文件"""
        # 保存当前配置
        self.summary_length = int(self.length_var.get())
        self.request_interval = int(self.interval_var.get())
        self.save_config()
        
        file_path = self.file_var.get()
        if not file_path:
            messagebox.showerror("错误", "请选择一个Markdown文件")
            return
        
        if not os.path.exists(file_path):
            messagebox.showerror("错误", "文件不存在")
            return
        
        # 切换到处理进度选项卡
        self.tabview.set("进度")
        
        # 清除日志
        self.log_text.delete("0.0", "end")
        self.log_message(f"开始处理文件: {file_path}")
        
        # 启动处理线程
        threading.Thread(target=self._process_single_file_worker, args=(file_path,), daemon=True).start()
    
    def _process_single_file_worker(self, file_path):
        """单文件处理工作线程"""
        try:
            self.update_status("正在处理文件...", 0.5)
            
            if self.process_markdown_file(file_path):
                self.update_status("处理完成", 1.0)
                messagebox.showinfo("成功", "文件处理完成！")
            else:
                self.update_status("处理失败", 0)
                messagebox.showerror("错误", "文件处理失败，查看日志了解详情")
        except Exception as e:
            self.update_status("处理错误", 0)
            self.log_message(f"处理错误: {str(e)}")
            messagebox.showerror("错误", f"处理错误: {str(e)}")
    
    def process_markdown_file(self, file_path):
        """处理Markdown文件，生成摘要"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除现有的摘要（如果有）
            content = re.sub(r'---\narticleGPT:.*?\n---\n', '', content, flags=re.DOTALL)
            
            # 获取活动模型
            if self.active_model not in self.models:
                self.log_message("错误: 活动模型未配置")
                return False
            
            model = self.models[self.active_model]
            self.log_message(f"使用模型: {model.name}")
            
            # 生成摘要
            summary = model.generate_summary(content, self.summary_length, self.prompt_template)
            
            # 添加摘要到文件
            new_content = f"---\narticleGPT: {summary}\nshow: true\n---\n\n{content}"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.log_message(f"✅ 成功处理: {file_path}")
            return True
        
        except Exception as e:
            self.log_message(f"❌ 处理失败 {file_path}: {str(e)}")
            return False
    
    def start_processing(self):
        """开始批量处理"""
        if self.is_processing:
            return
        
        # 更新配置
        self.summary_length = int(self.length_var.get())
        self.request_interval = int(self.interval_var.get())
        self.max_workers = int(self.workers_var.get())
        self.directory = self.dir_var.get()
        self.save_config()
        
        if not self.directory:
            messagebox.showerror("错误", "请选择一个目录")
            return
        
        # 切换到处理进度选项卡
        self.tabview.set("进度")
        
        # 清除日志和失败列表
        self.log_text.delete("0.0", "end")
        self.failed_files = []
        
        # 标记为处理中
        self.is_processing = True
        self.start_button.configure(state="disabled")
        self.retry_button.configure(state="disabled")
        
        # 启动处理线程
        threading.Thread(target=self._process_directory_worker, daemon=True).start()
    
    def _process_directory_worker(self):
        """目录处理工作线程"""
        try:
            # 查找所有Markdown文件
            markdown_files = list(Path(self.directory).rglob("*.md"))
            
            if not markdown_files:
                self.log_message("在选定目录中未找到Markdown文件")
                self.is_processing = False
                self.start_button.configure(state="normal")
                self.update_status("未找到文件")
                return
            
            total_files = len(markdown_files)
            self.log_message(f"找到{total_files}个Markdown文件。开始处理...")
            
            # 重置进度条
            self.update_status(f"正在处理{total_files}个文件...", 0)
            
            # 使用线程池处理文件
            completed = 0
            failed = 0
            
            # 将Path对象转换为字符串
            markdown_files = [str(f) for f in markdown_files]
            
            # 批量处理以控制并发
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有文件进行处理
                future_to_file = {executor.submit(self.process_markdown_file, file): file for file in markdown_files}
                
                # 处理完成的任务
                for i, future in enumerate(concurrent.futures.as_completed(future_to_file)):
                    file = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            completed += 1
                        else:
                            failed += 1
                            self.failed_files.append(file)
                    except Exception as e:
                        self.log_message(f"❌ 处理错误 {file}: {str(e)}")
                        failed += 1
                        self.failed_files.append(file)
                    
                    # 更新进度
                    progress = (i + 1) / total_files
                    self.update_status(f"正在处理 {i+1}/{total_files}", progress)
                    
                    # 小延迟以避免UI冻结
                    time.sleep(0.1)
            
            # 处理完成
            self.log_message(f"\n处理完成！")
            self.log_message(f"成功处理: {completed}")
            self.log_message(f"失败: {failed}")
            
            self.update_status(f"处理完成: {completed}成功, {failed}失败", 1.0)
            
            # 显示通知
            messagebox.showinfo("批量处理完成", f"处理完成！\n成功: {completed}\n失败: {failed}")
            
            # 启用重试按钮（如果有失败的文件）
            if self.failed_files:
                self.retry_button.configure(state="normal")
        
        except Exception as e:
            self.log_message(f"处理错误: {str(e)}")
            self.update_status("处理错误", 0)
        
        finally:
            self.is_processing = False
            self.start_button.configure(state="normal")
    
    def retry_failed(self):
        """重试失败的文件"""
        if not self.failed_files:
            return
        
        # 禁用重试按钮
        self.retry_button.configure(state="disabled")
        
        # 切换到处理进度选项卡
        self.tabview.set("进度")
        
        self.log_message("\n重试失败的文件...")
        
        # 复制失败文件列表并清空它
        failed_files = self.failed_files.copy()
        self.failed_files = []
        
        # 启动重试线程
        threading.Thread(target=self._retry_failed_worker, args=(failed_files,), daemon=True).start()
    
    def _retry_failed_worker(self, failed_files):
        """重试失败文件的工作线程"""
        try:
            total_files = len(failed_files)
            
            completed = 0
            failed = 0
            
            # 使用线程池处理重试
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有文件进行处理
                future_to_file = {executor.submit(self.process_markdown_file, file): file for file in failed_files}
                
                # 处理完成的任务
                for i, future in enumerate(concurrent.futures.as_completed(future_to_file)):
                    file = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            completed += 1
                        else:
                            failed += 1
                            self.failed_files.append(file)
                    except Exception as e:
                        self.log_message(f"❌ 处理错误 {file}: {str(e)}")
                        failed += 1
                        self.failed_files.append(file)
                    
                    # 更新进度
                    progress = (i + 1) / total_files
                    self.update_status(f"重试中 {i+1}/{total_files}", progress)
                    
                    # 小延迟以避免UI冻结
                    time.sleep(0.1)
            
            # 重试完成
            self.log_message(f"\n重试完成！")
            self.log_message(f"成功处理: {completed}")
            self.log_message(f"失败: {failed}")
            
            self.update_status(f"重试完成: {completed}成功, {failed}失败", 1.0)
            
            # 显示通知
            messagebox.showinfo("重试完成", f"重试完成！\n成功: {completed}\n失败: {failed}")
            
            # 启用重试按钮（如果还有失败的文件）
            if self.failed_files:
                self.retry_button.configure(state="normal")
        
        except Exception as e:
            self.log_message(f"重试错误: {str(e)}")
            self.update_status("重试错误", 0)
    
    def run(self):
        """运行应用程序"""
        self.window.mainloop()

def main():
    """主函数"""
    app = MarkdownSummarizer()
    app.run()

if __name__ == "__main__":
    main()