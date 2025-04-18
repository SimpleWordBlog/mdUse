import os
import json
import re
import time
import logging
import threading
from datetime import datetime
from queue import Queue
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
ctk.set_appearance_mode("System")  # 自动适应系统主题
ctk.set_default_color_theme("blue")  # 默认颜色主题

class AIModelConfig:
    """AI模型配置基类"""
    def __init__(self, name, base_url, api_key_name=None):
        self.name = name
        self.base_url = base_url
        self.api_key_name = api_key_name or f"{name.upper()}_API_KEY"
        self.api_key = os.getenv(self.api_key_name, "")
        
    def get_client(self, api_key=None):
        """获取API客户端"""
        raise NotImplementedError("子类必须实现get_client方法")
    
    def generate_summary(self, content, max_length, api_key=None):
        """生成摘要"""
        raise NotImplementedError("子类必须实现generate_summary方法")
    
    def to_dict(self):
        """转换为字典，用于保存配置"""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "api_key_name": self.api_key_name,
            "api_key": self.api_key
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建配置"""
        instance = cls(data["name"], data["base_url"], data["api_key_name"])
        instance.api_key = data.get("api_key", "")
        return instance
    
class OpenAICompatibleModel(AIModelConfig):
    """OpenAI兼容的模型配置"""
    def __init__(self, name, base_url, api_key_name=None, models=None):
        super().__init__(name, base_url, api_key_name)
        self.models = models or []
        self.selected_model = self.models[0] if self.models else ""
        
    def get_client(self, api_key=None):
        """获取OpenAI兼容的客户端"""
        from openai import OpenAI
        return OpenAI(
            api_key=api_key or self.api_key,
            base_url=self.base_url
        )
    
    def generate_summary(self, content, max_length, api_key=None):
        """使用OpenAI兼容API生成摘要"""
        client = self.get_client(api_key)
        
        prompt = f"""请为以下markdown内容生成一个简洁、紧凑的摘要，必须遵循以下要求：
1. 字数严格控制在{max_length}字以内，简洁
2. 不要使用markdown语法和格式（不要使用标题、列表符号、强调符号等）
3. 使用连贯的、流畅的叙述性文本
4. 只提取文档中最核心、最重要的信息
5. 使用客观、简洁的语言风格
6. 摘要应该是一段完整的文字，不要分段,不要有空格,不要有空行，始终紧凑前面的内容位置。

以下是需要摘要的内容：

{content}"""

        response = client.chat.completions.create(
            model=self.selected_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的文档摘要生成助手。你的任务是提取文档的核心信息，并生成简洁、紧凑、易读的摘要。不要使用任何markdown格式，只生成纯文本摘要。"
                },
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content.strip()
    
    def to_dict(self):
        """转换为字典，用于保存配置"""
        data = super().to_dict()
        data.update({
            "models": self.models,
            "selected_model": self.selected_model
        })
        return data
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建配置"""
        instance = cls(
            data["name"], 
            data["base_url"], 
            data["api_key_name"], 
            data.get("models", [])
        )
        instance.api_key = data.get("api_key", "")
        instance.selected_model = data.get("selected_model", instance.selected_model)
        return instance

class AnthropicModel(AIModelConfig):
    """Anthropic模型配置"""
    def __init__(self, name="anthropic", base_url="https://api.anthropic.com", api_key_name=None, models=None):
        super().__init__(name, base_url, api_key_name or "ANTHROPIC_API_KEY")
        self.models = models or ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        self.selected_model = self.models[0] if self.models else ""
    
    def get_client(self, api_key=None):
        """获取Anthropic客户端"""
        from anthropic import Anthropic
        return Anthropic(api_key=api_key or self.api_key)
    
    def generate_summary(self, content, max_length, api_key=None):
        """使用Anthropic API生成摘要"""
        client = self.get_client(api_key)
        
        prompt = f"""请为以下markdown内容生成一个简洁、紧凑的摘要，必须遵循以下要求：
1. 字数严格控制在{max_length}字以内，简洁
2. 不要使用markdown语法和格式（不要使用标题、列表符号、强调符号等）
3. 使用连贯的、流畅的叙述性文本
4. 只提取文档中最核心、最重要的信息
5. 使用客观、简洁的语言风格
6. 摘要应该是一段完整的文字，不要分段,不要有空格,不要有空行，始终紧凑前面的内容位置。

以下是需要摘要的内容：

{content}"""

        response = client.messages.create(
            model=self.selected_model,
            max_tokens=1024,
            system="你是一个专业的文档摘要生成助手。你的任务是提取文档的核心信息，并生成简洁、紧凑、易读的摘要。不要使用任何markdown格式，只生成纯文本摘要。",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.content[0].text
    
    def to_dict(self):
        """转换为字典，用于保存配置"""
        data = super().to_dict()
        data.update({
            "models": self.models,
            "selected_model": self.selected_model
        })
        return data

class GeminiModel(AIModelConfig):
    """Google Gemini模型配置"""
    def __init__(self, name="gemini", base_url=None, api_key_name=None, models=None):
        super().__init__(name, base_url, api_key_name or "GEMINI_API_KEY")
        self.models = models or ["gemini-1.5-pro", "gemini-1.5-flash"]
        self.selected_model = self.models[0] if self.models else ""
    
    def get_client(self, api_key=None):
        """获取Google Gemini客户端"""
        import google.generativeai as genai
        genai.configure(api_key=api_key or self.api_key)
        return genai
    
    def generate_summary(self, content, max_length, api_key=None):
        """使用Google Gemini API生成摘要"""
        genai = self.get_client(api_key)
        
        prompt = f"""请为以下markdown内容生成一个简洁、紧凑的摘要，必须遵循以下要求：
1. 字数严格控制在{max_length}字以内，简洁
2. 不要使用markdown语法和格式（不要使用标题、列表符号、强调符号等）
3. 使用连贯的、流畅的叙述性文本
4. 只提取文档中最核心、最重要的信息
5. 使用客观、简洁的语言风格
6. 摘要应该是一段完整的文字，不要分段,不要有空格,不要有空行，始终紧凑前面的内容位置。

以下是需要摘要的内容：

{content}"""

        model = genai.GenerativeModel(self.selected_model)
        response = model.generate_content(prompt)
        
        return response.text.strip()

# 预定义的模型配置
DEFAULT_MODEL_CONFIGS = [
    OpenAICompatibleModel(
        "DeepSeek-v3", 
        "https://api.suanli.cn/v1", 
        "DEEPSEEK_API_KEY",
        ["deepseek-v3"]
    ),
]

class ModelManager:
    """模型管理器"""
    def __init__(self):
        self.models = {}
        self.active_model = None
        
    def add_model(self, model_config):
        """添加模型配置"""
        self.models[model_config.name] = model_config
        if not self.active_model:
            self.active_model = model_config.name
    
    def get_model(self, name=None):
        """获取指定名称的模型配置"""
        name = name or self.active_model
        return self.models.get(name)
    
    def set_active_model(self, name):
        """设置当前活动模型"""
        if name in self.models:
            self.active_model = name
            return True
        return False
    
    def get_model_names(self):
        """获取所有模型名称"""
        return list(self.models.keys())
    
    def to_dict(self):
        """转换为字典，用于保存配置"""
        return {
            "models": {name: model.to_dict() for name, model in self.models.items()},
            "active_model": self.active_model
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建模型管理器"""
        manager = cls()
        
        # 处理模型配置
        models_data = data.get("models", {})
        for name, model_data in models_data.items():
            if model_data.get("name") == "anthropic":
                model = AnthropicModel.from_dict(model_data)
            elif model_data.get("name") == "gemini":
                model = GeminiModel.from_dict(model_data)
            else:
                model = OpenAICompatibleModel.from_dict(model_data)
            manager.add_model(model)
        
        # 设置活动模型
        active_model = data.get("active_model")
        if active_model and active_model in manager.models:
            manager.active_model = active_model
        
        return manager

class ModelConfigFrame(ctk.CTkFrame):
    """模型配置界面"""
    def __init__(self, parent, model_manager, callback=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.callback = callback
        self.api_key_entries = {}
        self.model_comboboxes = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        # 标题
        title = ctk.CTkLabel(self, text="AI模型配置", font=("Helvetica", 16, "bold"))
        title.pack(pady=(10, 20))
        
        # 模型选择
        model_select_frame = ctk.CTkFrame(self)
        model_select_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(model_select_frame, text="当前使用的模型:").pack(side="left", padx=5)
        
        self.active_model_var = ctk.StringVar(value=self.model_manager.active_model)
        self.active_model_dropdown = ctk.CTkComboBox(
            model_select_frame, 
            values=self.model_manager.get_model_names(),
            variable=self.active_model_var,
            command=self.on_active_model_changed
        )
        self.active_model_dropdown.pack(side="left", fill="x", expand=True, padx=5)
        
        # 添加新模型按钮
        add_button = ctk.CTkButton(model_select_frame, text="添加模型", command=self.add_new_model)
        add_button.pack(side="right", padx=5)
        
        # 模型参数设置
        self.models_frame = ctk.CTkScrollableFrame(self)
        self.models_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # 创建各模型配置界面
        self.refresh_models_ui()
    
    def refresh_models_ui(self):
        """刷新模型配置界面"""
        # 清空当前UI
        for widget in self.models_frame.winfo_children():
            widget.destroy()
        
        self.api_key_entries = {}
        self.model_comboboxes = {}
        
        # 更新活动模型下拉框
        self.active_model_dropdown.configure(values=self.model_manager.get_model_names())
        self.active_model_var.set(self.model_manager.active_model)
        
        # 为每个模型创建配置区域
        for i, name in enumerate(self.model_manager.get_model_names()):
            model = self.model_manager.get_model(name)
            
            # 创建模型配置框架
            model_frame = ctk.CTkFrame(self.models_frame)
            model_frame.pack(fill="x", pady=10, padx=5)
            
            # 模型标题和删除按钮
            header_frame = ctk.CTkFrame(model_frame)
            header_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(header_frame, text=f"{name}", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
            
            if len(self.model_manager.models) > 1:  # 至少保留一个模型
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
            
            ctk.CTkLabel(key_frame, text="API密钥:").pack(side="left", padx=5)
            
            api_key_entry = ctk.CTkEntry(key_frame, width=300, show="*")
            api_key_entry.insert(0, model.api_key)
            api_key_entry.pack(side="left", fill="x", expand=True, padx=5)
            
            self.api_key_entries[name] = api_key_entry
            
            # 模型选择（如果有）
            if hasattr(model, 'models') and model.models:
                model_frame = ctk.CTkFrame(model_frame)
                model_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(model_frame, text="模型:").pack(side="left", padx=5)
                
                model_var = ctk.StringVar(value=model.selected_model)
                model_combobox = ctk.CTkComboBox(
                    model_frame, 
                    values=model.models,
                    variable=model_var,
                    command=lambda value, m=name: self.on_model_selection_changed(m, value)
                )
                model_combobox.pack(side="left", fill="x", expand=True, padx=5)
                
                self.model_comboboxes[name] = model_combobox
            
            # API基础URL（如果不是Gemini）
            if hasattr(model, 'base_url') and model.base_url and model.name != "gemini":
                url_frame = ctk.CTkFrame(model_frame)
                url_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(url_frame, text="API基础URL:").pack(side="left", padx=5)
                
                url_entry = ctk.CTkEntry(url_frame, width=300)
                url_entry.insert(0, model.base_url)
                url_entry.pack(side="left", fill="x", expand=True, padx=5)
                
                url_entry.configure(state="readonly")  # 目前不允许修改URL
    
    def on_active_model_changed(self, value):
        """当活动模型改变时"""
        self.model_manager.set_active_model(value)
        if self.callback:
            self.callback()
    
    def on_model_selection_changed(self, model_name, value):
        """当模型选择改变时"""
        model = self.model_manager.get_model(model_name)
        if model and hasattr(model, 'selected_model'):
            model.selected_model = value
    
    def add_new_model(self):
        """添加新模型"""
        dialog = ModelAddDialog(self)
        dialog.wait_window()
        
        if dialog.result:
            model_name = dialog.result["name"]
            base_url = dialog.result["base_url"]
            api_key = dialog.result["api_key"]
            model_id = dialog.result["model_id"]
            
            # 确保名称唯一
            if model_name in self.model_manager.get_model_names():
                messagebox.showerror("错误", f"模型名称 '{model_name}' 已存在")
                return
            
            # 创建新模型配置
            model = OpenAICompatibleModel(
                model_name, 
                base_url, 
                f"{model_name.upper()}_API_KEY",
                [model_id]
            )
            
            # 设置API密钥
            model.api_key = api_key
            
            # 添加新模型
            self.model_manager.add_model(model)
            self.refresh_models_ui()
            
            if self.callback:
                self.callback()
    
    def delete_model(self, model_name):
        """删除模型"""
        if len(self.model_manager.models) <= 1:
            messagebox.showerror("错误", "至少需要保留一个模型配置")
            return
        
        result = messagebox.askyesno("确认", f"确定要删除模型 '{model_name}' 吗？")
        if result:
            if model_name == self.model_manager.active_model:
                # 如果删除的是当前活动模型，则切换到第一个可用模型
                available_models = [m for m in self.model_manager.get_model_names() if m != model_name]
                if available_models:
                    self.model_manager.set_active_model(available_models[0])
            
            # 删除模型
            if model_name in self.model_manager.models:
                del self.model_manager.models[model_name]
                
                self.refresh_models_ui()
                
                if self.callback:
                    self.callback()
    
    def save_changes(self):
        """保存对模型配置的更改"""
        for name, entry in self.api_key_entries.items():
            model = self.model_manager.get_model(name)
            if model:
                model.api_key = entry.get()
        
        for name, combobox in self.model_comboboxes.items():
            model = self.model_manager.get_model(name)
            if model and hasattr(model, 'selected_model'):
                model.selected_model = combobox.get()

class ModelAddDialog(ctk.CTkToplevel):
    """添加新模型对话框"""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("添加新模型")
        self.geometry("500x400")
        self.grab_set()  # 模态对话框
        
        self.result = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        # 标题
        title = ctk.CTkLabel(self, text="添加新AI模型", font=("Helvetica", 16, "bold"))
        title.pack(pady=(20, 20))
        
        # 模型名称
        name_frame = ctk.CTkFrame(self)
        name_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(name_frame, text="模型名称:").pack(side="left", padx=5)
        
        self.name_entry = ctk.CTkEntry(name_frame)
        self.name_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # API基础URL
        base_url_frame = ctk.CTkFrame(self)
        base_url_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(base_url_frame, text="API基础URL:").pack(side="left", padx=5)
        
        self.base_url_entry = ctk.CTkEntry(base_url_frame)
        self.base_url_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # API密钥
        api_key_frame = ctk.CTkFrame(self)
        api_key_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(api_key_frame, text="API密钥:").pack(side="left", padx=5)
        
        self.api_key_entry = ctk.CTkEntry(api_key_frame, show="*")
        self.api_key_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 模型ID
        model_id_frame = ctk.CTkFrame(self)
        model_id_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(model_id_frame, text="模型ID:").pack(side="left", padx=5)
        
        self.model_id_entry = ctk.CTkEntry(model_id_frame)
        self.model_id_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 按钮
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(button_frame, text="取消", command=self.cancel).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="确定", command=self.confirm).pack(side="right", padx=10)
    
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
        
        if not model_name:
            messagebox.showerror("错误", "模型名称不能为空")
            return
        
        if not base_url:
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
            "model_id": model_id
        }
        
        self.destroy()

class MarkdownSummarizer:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title("Markdown 摘要生成器")
        self.window.geometry("1024x768")
        
        # 初始化变量
        self.failed_files = []
        self.is_processing = False
        self.process_queue = Queue()
        
        # 加载配置
        self.load_config()
        
        # 设置日志
        self.setup_logging()
        
        # 设置UI
        self.setup_ui()
    
    def setup_logging(self):
        """设置日志，使用UTF-8编码"""
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
                
                # 加载模型配置
                self.model_manager = ModelManager.from_dict(config.get("model_manager", {}))
                
                # 如果没有模型，添加默认模型
                if not self.model_manager.models:
                    for model_config in DEFAULT_MODEL_CONFIGS:
                        self.model_manager.add_model(model_config)
        except FileNotFoundError:
            # 创建默认配置
            self.summary_length = 200
            self.directory = ""
            self.request_interval = 3
            self.model_manager = ModelManager()
            
            # 添加默认模型
            for model_config in DEFAULT_MODEL_CONFIGS:
                self.model_manager.add_model(model_config)
    
    def save_config(self):
        """保存配置"""
        # 保存之前更新模型配置
        if hasattr(self, 'model_config_frame'):
            self.model_config_frame.save_changes()
        
        config = {
            "summary_length": self.summary_length,
            "directory": self.directory,
            "request_interval": self.request_interval,
            "model_manager": self.model_manager.to_dict()
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return True
    
    def setup_ui(self):
        """设置用户界面"""
        # 主要容器
        self.main_container = ctk.CTkFrame(self.window)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 标题
        title = ctk.CTkLabel(
            self.main_container, 
            text="Markdown 摘要生成器", 
            font=("Helvetica", 24, "bold")
        )
        title.pack(pady=(10, 20))
        
        # 创建选项卡控件
        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 创建选项卡
        self.config_tab = self.tabview.add("配置")
        self.model_tab = self.tabview.add("模型设置")
        self.processing_tab = self.tabview.add("处理进度")
        
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
        
        # 不使用图标，只用纯文本标签
        ctk.CTkLabel(summary_frame, text="摘要设置", font=("Helvetica", 16, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # 摘要长度
        length_frame = ctk.CTkFrame(summary_frame)
        length_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(length_frame, text="摘要长度（字符数）:").pack(side="left", padx=5)
        
        self.length_var = ctk.StringVar(value=str(self.summary_length))
        length_entry = ctk.CTkEntry(length_frame, textvariable=self.length_var)
        length_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 请求间隔时间
        interval_frame = ctk.CTkFrame(summary_frame)
        interval_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(interval_frame, text="请求间隔时间（秒）:").pack(side="left", padx=5)
        
        self.interval_var = ctk.StringVar(value=str(self.request_interval))
        interval_spinbox = ctk.CTkOptionMenu(
            interval_frame, 
            values=[str(i) for i in range(1, 11)],
            variable=self.interval_var
        )
        interval_spinbox.pack(side="left", padx=5)
        
        # 单文件处理
        file_frame = ctk.CTkFrame(self.config_tab)
        file_frame.pack(fill="x", padx=20, pady=10)
        
        # 不使用图标
        ctk.CTkLabel(file_frame, text="单个文件处理", font=("Helvetica", 16, "bold")).pack(anchor="w", padx=10, pady=5)
        
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
        
        # 不使用图标
        ctk.CTkLabel(batch_frame, text="批量处理", font=("Helvetica", 16, "bold")).pack(anchor="w", padx=10, pady=5)
        
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
            command=lambda: self.save_config_with_message()
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
        # 创建模型配置界面
        self.model_config_frame = ModelConfigFrame(
            self.model_tab, 
            self.model_manager,
            callback=self.on_model_config_changed
        )
        self.model_config_frame.pack(fill="both", expand=True)
    
    def setup_processing_tab(self):
        """设置处理进度选项卡"""
        # 状态标签
        self.status_label = ctk.CTkLabel(
            self.processing_tab,
            text="就绪",
            font=("Helvetica", 14)
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
    
    def on_model_config_changed(self):
        """当模型配置变更时的回调"""
        self.save_config()
    
    def save_config_with_message(self):
        """保存配置并显示提示"""
        # 更新配置值
        self.summary_length = int(self.length_var.get())
        self.request_interval = int(self.interval_var.get())
        self.directory = self.dir_var.get()
        
        if self.save_config():
            messagebox.showinfo("成功", "配置已保存")
    
    def browse_file(self):
        """浏览选择Markdown文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
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
        """记录消息到界面和日志文件"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 添加到界面
        self.log_text.insert("end", formatted_message + "\n")
        self.log_text.see("end")
        
        # 记录到日志文件
        logging.info(message)
    
    def update_status(self, message, progress=None):
        """更新状态信息和进度条"""
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
        
        # 切换到处理选项卡
        self.tabview.set("处理进度")
        
        # 清空日志
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
                messagebox.showerror("错误", "文件处理失败，请查看日志了解详情")
        except Exception as e:
            self.update_status("处理出错", 0)
            self.log_message(f"处理过程出错: {str(e)}")
            messagebox.showerror("错误", f"处理过程出错: {str(e)}")
    
    def process_markdown_file(self, file_path):
        """处理Markdown文件，生成摘要"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除现有的摘要信息（如果有）
            content = re.sub(r'---\narticleGPT:.*?\n---\n', '', content, flags=re.DOTALL)
            
            # 获取当前活动模型
            model = self.model_manager.get_model()
            if not model:
                self.log_message("错误：未配置AI模型")
                return False
            
            self.log_message(f"使用模型: {model.name}")
            
            # 生成摘要
            summary = model.generate_summary(content, self.summary_length)
            
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
        self.directory = self.dir_var.get()
        self.save_config()
        
        if not self.directory:
            messagebox.showerror("错误", "请选择一个目录")
            return
        
        # 切换到处理选项卡
        self.tabview.set("处理进度")
        
        # 清空日志和失败列表
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
            self.log_message(f"找到 {total_files} 个Markdown文件。开始处理...")
            
            # 重置进度条
            self.update_status(f"正在处理 {total_files} 个文件...", 0)
            
            # 清空队列
            with self.process_queue.mutex:
                self.process_queue.queue.clear()
            
            # 添加文件到队列
            for file_path in markdown_files:
                self.process_queue.put(str(file_path))
            
            # 获取请求间隔时间
            request_interval = self.request_interval
            
            completed = 0
            failed = 0
            
            # 处理队列中的文件
            while not self.process_queue.empty():
                file_path = self.process_queue.get()
                
                # 更新进度
                progress = completed / total_files
                self.update_status(f"正在处理 {completed+1}/{total_files}", progress)
                
                # 处理文件
                if self.process_markdown_file(file_path):
                    completed += 1
                else:
                    failed += 1
                    self.failed_files.append(file_path)
                
                # 添加请求间隔时间
                time.sleep(request_interval)
            
            # 完成处理
            self.log_message(f"\n处理完成！")
            self.log_message(f"成功处理: {completed}")
            self.log_message(f"失败: {failed}")
            
            self.update_status(f"处理完成: 成功 {completed}, 失败 {failed}", 1.0)
            
            # 添加弹窗通知
            messagebox.showinfo("批量处理完成", f"处理完成！\n成功: {completed}\n失败: {failed}")
            
            # 启用重试按钮（如果有失败的文件）
            if self.failed_files:
                self.retry_button.configure(state="normal")
        
        except Exception as e:
            self.log_message(f"处理过程出错: {str(e)}")
            self.update_status("处理出错", 0)
        
        finally:
            self.is_processing = False
            self.start_button.configure(state="normal")
    
    def retry_failed(self):
        """重试失败的文件"""
        if not self.failed_files:
            return
        
        # 禁用重试按钮
        self.retry_button.configure(state="disabled")
        
        # 切换到处理选项卡
        self.tabview.set("处理进度")
        
        self.log_message("\n开始重试失败的文件...")
        
        # 复制失败文件列表并清空
        failed_files = self.failed_files.copy()
        self.failed_files = []
        
        total_files = len(failed_files)
        
        # 启动重试线程
        threading.Thread(target=self._retry_failed_worker, args=(failed_files, total_files), daemon=True).start()
    
    def _retry_failed_worker(self, failed_files, total_files):
        """重试失败文件的工作线程"""
        try:
            # 获取请求间隔时间
            request_interval = self.request_interval
            
            completed = 0
            failed = 0
            
            for i, file_path in enumerate(failed_files):
                # 更新进度
                progress = i / total_files
                self.update_status(f"重试 {i+1}/{total_files}", progress)
                
                # 处理文件
                if self.process_markdown_file(file_path):
                    completed += 1
                else:
                    failed += 1
                    self.failed_files.append(file_path)
                
                # 添加请求间隔时间
                time.sleep(request_interval)
            
            # 完成处理
            self.log_message(f"\n重试完成！")
            self.log_message(f"成功处理: {completed}")
            self.log_message(f"失败: {failed}")
            
            self.update_status(f"重试完成: 成功 {completed}, 失败 {failed}", 1.0)
            
            # 添加弹窗通知
            messagebox.showinfo("重试完成", f"重试完成！\n成功: {completed}\n失败: {failed}")
            
            # 启用重试按钮（如果有失败的文件）
            if self.failed_files:
                self.retry_button.configure(state="normal")
        
        except Exception as e:
            self.log_message(f"重试过程出错: {str(e)}")
            self.update_status("重试出错", 0)
    
    def run(self):
        """运行应用程序"""
        self.window.mainloop()

def main():
    """主函数"""
    app = MarkdownSummarizer()
    app.run()

if __name__ == "__main__":
    main()