import streamlit as st
import requests
import json
import os
import base64
import tempfile
import time
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import threading
from queue import Queue
import concurrent.futures

# ==================== 配置 ====================
st.set_page_config(
    page_title="GitHub文本语音播放器 - 增强版",
    page_icon="🔊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 初始化Session State ====================
DEFAULT_SESSION_STATES = {
    'audio_file': None,
    'current_position': 0,
    'playback_state': {},
    'selected_file': "",
    'text_content': "",
    'tts_cache': {},
    'request_count': 0,
    'last_request_time': time.time(),
    'available_engines': [],
    'current_engine': "gTTS",
    'use_cache': True,
    'chunk_size': 400
}

for key, value in DEFAULT_SESSION_STATES.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==================== 缓存管理器 ====================
class CacheManager:
    """智能缓存管理器"""
    
    def __init__(self, cache_dir='.tts_cache', max_size_mb=100):
        self.cache_dir = cache_dir
        self.max_size = max_size_mb * 1024 * 1024  # 转换为字节
        self.cache_info_file = os.path.join(cache_dir, 'cache_info.json')
        self._init_cache()
    
    def _init_cache(self):
        """初始化缓存目录"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        if not os.path.exists(self.cache_info_file):
            self.cache_info = {}
            self._save_cache_info()
        else:
            with open(self.cache_info_file, 'r', encoding='utf-8') as f:
                self.cache_info = json.load(f)
        
        self._cleanup_old_cache()
    
    def _save_cache_info(self):
        """保存缓存信息"""
        with open(self.cache_info_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache_info, f, ensure_ascii=False, indent=2)
    
    def _cleanup_old_cache(self):
        """清理过期缓存"""
        try:
            current_time = time.time()
            to_delete = []
            total_size = 0
            
            for cache_key, info in list(self.cache_info.items()):
                cache_path = os.path.join(self.cache_dir, cache_key)
                if os.path.exists(cache_path):
                    # 检查是否过期（7天）
                    if current_time - info.get('timestamp', 0) > 7 * 24 * 3600:
                        to_delete.append(cache_key)
                    else:
                        total_size += os.path.getsize(cache_path)
                else:
                    to_delete.append(cache_key)
            
            # 如果超过最大大小，按时间清理
            if total_size > self.max_size:
                sorted_items = sorted(self.cache_info.items(), 
                                    key=lambda x: x[1].get('timestamp', 0))
                for cache_key, _ in sorted_items:
                    if total_size <= self.max_size * 0.8:  # 保留80%空间
                        break
                    cache_path = os.path.join(self.cache_dir, cache_key)
                    if os.path.exists(cache_path):
                        total_size -= os.path.getsize(cache_path)
                        to_delete.append(cache_key)
            
            # 删除文件
            for cache_key in to_delete:
                cache_path = os.path.join(self.cache_dir, cache_key)
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                if cache_key in self.cache_info:
                    del self.cache_info[cache_key]
            
            if to_delete:
                self._save_cache_info()
                st.toast(f"清理了 {len(to_delete)} 个缓存文件")
                
        except Exception as e:
            print(f"缓存清理失败: {e}")
    
    def get_cache_key(self, text: str, engine: str, lang: str) -> str:
        """生成缓存键"""
        content = f"{text[:500]}_{engine}_{lang}_{len(text)}"
        return hashlib.md5(content.encode('utf-8')).hexdigest() + '.mp3'
    
    def get_cached_audio(self, text: str, engine: str, lang: str) -> Optional[str]:
        """获取缓存的音频"""
        cache_key = self.get_cache_key(text, engine, lang)
        cache_path = os.path.join(self.cache_dir, cache_key)
        
        if os.path.exists(cache_path):
            # 更新访问时间
            self.cache_info[cache_key] = {
                'timestamp': time.time(),
                'engine': engine,
                'lang': lang,
                'text_length': len(text)
            }
            self._save_cache_info()
            return cache_path
        return None
    
    def save_to_cache(self, text: str, engine: str, lang: str, audio_path: str) -> str:
        """保存到缓存"""
        cache_key = self.get_cache_key(text, engine, lang)
        cache_path = os.path.join(self.cache_dir, cache_key)
        
        try:
            import shutil
            shutil.copy(audio_path, cache_path)
            
            self.cache_info[cache_key] = {
                'timestamp': time.time(),
                'engine': engine,
                'lang': lang,
                'text_length': len(text)
            }
            self._save_cache_info()
            
            return cache_path
        except Exception as e:
            print(f"缓存保存失败: {e}")
            return audio_path

# ==================== 多引擎TTS系统 ====================
class MultiEngineTTS:
    """多引擎TTS系统，支持故障转移"""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.engines = self._detect_available_engines()
        st.session_state.available_engines = list(self.engines.keys())
    
    def _detect_available_engines(self) -> Dict:
        """检测可用的TTS引擎"""
        engines = {}
        
        # 1. gTTS (主要)
        try:
            from gtts import gTTS
            engines['gTTS'] = {
                'name': 'gTTS (Google)',
                'function': self._use_gtts,
                'priority': 1,
                'languages': ['zh-cn', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru'],
                'requires_internet': True
            }
        except:
            pass
        
        # 2. Edge TTS (备用)
        try:
            import edge_tts
            engines['edge_tts'] = {
                'name': 'Edge TTS (微软)',
                'function': self._use_edge_tts,
                'priority': 2,
                'languages': ['zh-CN', 'en-US', 'ja-JP', 'ko-KR'],
                'requires_internet': True
            }
        except:
            pass
        
        # 3. pyttsx3 (离线备用)
        try:
            import pyttsx3
            engines['pyttsx3'] = {
                'name': 'pyttsx3 (离线)',
                'function': self._use_pyttsx3,
                'priority': 3,
                'languages': ['zh', 'en'],
                'requires_internet': False
            }
        except:
            pass
        
        # 4. 本地TTS API (自定义)
        engines['local_api'] = {
            'name': '本地API',
            'function': self._use_local_api,
            'priority': 4,
            'languages': ['zh-cn', 'en'],
            'requires_internet': False
        }
        
        return engines
    
    def _rate_limit(self):
        """智能速率限制"""
        current_time = time.time()
        time_since_last = current_time - st.session_state.last_request_time
        
        # 动态调整等待时间
        if st.session_state.request_count > 10:
            wait_time = 5.0
        elif st.session_state.request_count > 5:
            wait_time = 3.0
        elif time_since_last < 2.0:  # 最少间隔2秒
            wait_time = 2.0 - time_since_last
        else:
            wait_time = 0
        
        if wait_time > 0:
            with st.spinner(f"⏳ 请求限制中，等待 {wait_time:.1f} 秒..."):
                time.sleep(wait_time)
        
        st.session_state.last_request_time = time.time()
        st.session_state.request_count += 1
    
    def _use_gtts(self, text: str, lang: str = 'zh-cn') -> Optional[str]:
        """使用gTTS引擎"""
        try:
            from gtts import gTTS
            
            # 速率限制
            self._rate_limit()
            
            # 清理文本
            text = text.strip()
            if not text or len(text) > 5000:
                return None
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_path = tmp_file.name
            
            # 生成语音
            tts = gTTS(
                text=text,
                lang=lang if lang in ['zh-cn', 'en'] else 'en',
                slow=False,
                lang_check=False
            )
            
            tts.save(temp_path)
            return temp_path
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                st.warning("🚫 gTTS API限制，将尝试其他引擎...")
                return None
            else:
                st.error(f"gTTS错误: {error_msg}")
                return None
    
    def _use_edge_tts(self, text: str, lang: str = 'zh-CN') -> Optional[str]:
        """使用Edge TTS引擎"""
        try:
            import asyncio
            import edge_tts
            
            # 速率限制
            self._rate_limit()
            
            # 清理文本
            text = text.strip()
            if not text:
                return None
            
            # 映射语言到voice
            voice_map = {
                'zh-CN': 'zh-CN-XiaoxiaoNeural',
                'en-US': 'en-US-JennyNeural',
                'ja-JP': 'ja-JP-NanamiNeural',
                'ko-KR': 'ko-KR-SunHiNeural'
            }
            
            voice = voice_map.get(lang, 'zh-CN-XiaoxiaoNeural')
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_path = tmp_file.name
            
            # 异步生成语音
            async def generate():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(temp_path)
            
            asyncio.run(generate())
            return temp_path
            
        except Exception as e:
            st.warning(f"Edge TTS失败: {e}")
            return None
    
    def _use_pyttsx3(self, text: str, lang: str = 'zh') -> Optional[str]:
        """使用pyttsx3引擎（离线）"""
        try:
            import pyttsx3
            
            # 清理文本
            text = text.strip()
            if not text:
                return None
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_path = tmp_file.name
            
            # 初始化引擎
            engine = pyttsx3.init()
            
            # 配置引擎
            if lang == 'zh':
                # 尝试设置中文语音（如果有）
                voices = engine.getProperty('voices')
                for voice in voices:
                    if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                        engine.setProperty('voice', voice.id)
                        break
            
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 0.9)
            
            # 保存到文件
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            
            return temp_path
            
        except Exception as e:
            st.warning(f"pyttsx3失败: {e}")
            return None
    
    def _use_local_api(self, text: str, lang: str = 'zh-cn') -> Optional[str]:
        """使用本地TTS API（可配置）"""
        # 这里可以配置你自己的TTS API
        api_url = st.session_state.get('local_api_url', '')
        
        if not api_url:
            return None
        
        try:
            # 示例：调用本地部署的TTS服务
            payload = {
                'text': text[:1000],  # 限制长度
                'lang': lang,
                'speed': 1.0
            }
            
            response = requests.post(
                api_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                    tmp_file.write(response.content)
                    return tmp_file.name
            
        except:
            pass
        
        return None
    
    def text_to_speech(self, text: str, engine: str = None, lang: str = 'zh-cn', 
                      use_cache: bool = True) -> Optional[str]:
        """智能文本转语音"""
        
        # 检查缓存
        if use_cache and st.session_state.use_cache:
            cached = self.cache_manager.get_cached_audio(text, engine or st.session_state.current_engine, lang)
            if cached:
                st.toast("🎯 使用缓存音频", icon="✅")
                return cached
        
        # 选择引擎
        if engine is None:
            engine = st.session_state.current_engine
        
        if engine not in self.engines:
            st.error(f"引擎 {engine} 不可用")
            engine = st.session_state.available_engines[0] if st.session_state.available_engines else 'gTTS'
        
        # 尝试主引擎
        engine_func = self.engines[engine]['function']
        result = engine_func(text, lang)
        
        # 如果失败，尝试其他引擎
        if result is None and len(self.engines) > 1:
            st.info(f"正在尝试备用引擎...")
            for alt_engine, info in sorted(self.engines.items(), key=lambda x: x[1]['priority']):
                if alt_engine != engine:
                    alt_result = info['function'](text, lang)
                    if alt_result:
                        st.success(f"✓ 使用 {info['name']}")
                        result = alt_result
                        break
        
        # 保存到缓存
        if result and use_cache and st.session_state.use_cache:
            result = self.cache_manager.save_to_cache(text, engine, lang, result)
        
        return result

# ==================== 文本处理器 ====================
class TextProcessor:
    """智能文本处理器"""
    
    @staticmethod
    def smart_chunk(text: str, max_chars: int = 400) -> List[str]:
        """智能分块文本"""
        if not text:
            return []
        
        text = text.strip()
        if len(text) <= max_chars:
            return [text]
        
        chunks = []
        
        # 按段落分割
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            if len(paragraph) <= max_chars:
                chunks.append(paragraph)
            else:
                # 按句子分割
                sentences = re.split(r'(?<=[。！？；.!?;])', paragraph)
                current_chunk = ""
                
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) <= max_chars:
                        current_chunk += sentence
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = sentence
                
                if current_chunk:
                    chunks.append(current_chunk)
        
        # 合并过小的块
        merged_chunks = []
        current_merge = ""
        
        for chunk in chunks:
            if len(current_merge) + len(chunk) <= max_chars:
                current_merge += " " + chunk if current_merge else chunk
            else:
                if current_merge:
                    merged_chunks.append(current_merge)
                current_merge = chunk
        
        if current_merge:
            merged_chunks.append(current_merge)
        
        return merged_chunks
    
    @staticmethod
    def estimate_tts_time(text: str, chars_per_second: int = 15) -> float:
        """估计TTS生成时间"""
        return len(text) / chars_per_second

# ==================== GitHub阅读器 ====================
class GitHubReader:
    """GitHub文件阅读器"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def parse_repo_url(self, url: str) -> Optional[tuple]:
        """解析GitHub URL"""
        patterns = [
            r'github\.com/([^/]+)/([^/]+)(?:/tree/[^/]+/(.+))?',
            r'https://github\.com/([^/]+)/([^/]+)(?:/tree/[^/]+/(.+))?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                owner, repo = match.group(1), match.group(2)
                path = match.group(3) if match.group(3) else ""
                return owner, repo, path
        
        return None
    
    def get_files(self, repo_url: str) -> List[Dict]:
        """获取仓库中的txt文件"""
        parsed = self.parse_repo_url(repo_url)
        if not parsed:
            return []
        
        owner, repo, path = parsed
        
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            response = requests.get(api_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                contents = response.json()
                files = []
                
                for item in contents:
                    if item['type'] == 'file' and item['name'].lower().endswith('.txt'):
                        files.append({
                            'name': item['name'],
                            'path': item['path'],
                            'url': item['download_url'],
                            'size': item['size']
                        })
                
                return files
            else:
                st.error(f"GitHub API错误: {response.status_code}")
                return []
                
        except Exception as e:
            st.error(f"连接失败: {str(e)}")
            return []

# ==================== 播放管理器 ====================
class PlaybackManager:
    """播放状态管理器"""
    
    def __init__(self, state_file='playback_state.json'):
        self.state_file = state_file
        self.load_state()
    
    def load_state(self):
        """加载播放状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    st.session_state.playback_state = json.load(f)
        except:
            st.session_state.playback_state = {}
    
    def save_state(self):
        """保存播放状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(st.session_state.playback_state, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def update_position(self, filepath: str, position: int, audio_file: str = None):
        """更新播放位置"""
        st.session_state.playback_state[filepath] = {
            'position': position,
            'timestamp': time.time(),
            'audio_file': audio_file
        }
        self.save_state()
    
    def get_position(self, filepath: str) -> int:
        """获取播放位置"""
        return st.session_state.playback_state.get(filepath, {}).get('position', 0)

# ==================== Streamlit界面 ====================
def main():
    st.title("🔊 GitHub文本语音播放器 - 增强版")
    st.markdown("---")
    
    # 初始化管理器
    tts_system = MultiEngineTTS()
    text_processor = TextProcessor()
    github_reader = GitHubReader()
    playback_manager = PlaybackManager()
    
    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 设置")
        
        # 显示状态
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.metric("缓存命中", f"{len(tts_system.cache_manager.cache_info)}")
        with col_stat2:
            st.metric("请求计数", st.session_state.request_count)
        
        # TTS引擎选择
        st.subheader("🎙️ TTS引擎")
        if st.session_state.available_engines:
            engine_options = [tts_system.engines[e]['name'] for e in st.session_state.available_engines]
            selected_engine_name = st.selectbox(
                "选择引擎",
                engine_options,
                index=0
            )
            
            # 找到对应的引擎key
            for key, info in tts_system.engines.items():
                if info['name'] == selected_engine_name:
                    st.session_state.current_engine = key
                    break
        else:
            st.warning("未检测到TTS引擎，请安装gTTS")
        
        # 缓存设置
        st.subheader("💾 缓存设置")
        st.session_state.use_cache = st.checkbox("启用缓存", value=True)
        if st.button("清理缓存", type="secondary"):
            tts_system.cache_manager._cleanup_old_cache()
            st.rerun()
        
        # 文本处理设置
        st.subheader("📄 文本处理")
        st.session_state.chunk_size = st.slider(
            "分块大小（字符）",
            min_value=200,
            max_value=1000,
            value=400,
            step=50,
            help="较小的分块可避免API限制"
        )
        
        st.markdown("---")
        
        # 文件来源选择
        st.subheader("📂 文件来源")
        source = st.radio(
            "选择来源",
            ["GitHub仓库", "本地文件", "直接输入"],
            horizontal=True
        )
        
        if source == "GitHub仓库":
            repo_url = st.text_input(
                "GitHub仓库URL",
                placeholder="https://github.com/Mestas/Books",
                help="可包含子目录路径"
            )
            
            if repo_url and st.button("🔄 获取文件列表", type="primary"):
                with st.spinner("正在获取文件..."):
                    files = github_reader.get_files(repo_url)
                    if files:
                        st.session_state.github_files = files
                        st.success(f"找到 {len(files)} 个文件")
                    else:
                        st.error("未找到txt文件")
        
        elif source == "本地文件":
            uploaded_file = st.file_uploader(
                "上传文本文件",
                type=['txt', 'md', 'text'],
                help="支持.txt, .md, .text格式"
            )
            if uploaded_file:
                st.session_state.text_content = uploaded_file.read().decode('utf-8')
                st.session_state.selected_file = uploaded_file.name
        
        elif source == "直接输入":
            direct_text = st.text_area(
                "输入文本",
                height=150,
                placeholder="在此输入要转换的文本..."
            )
            if direct_text:
                st.session_state.text_content = direct_text
                st.session_state.selected_file = "direct_input.txt"
        
        # 显示文件列表
        if 'github_files' in st.session_state:
            st.subheader("📋 文件列表")
            for file in st.session_state.github_files[:10]:  # 限制显示数量
                if st.button(f"📄 {file['name']} ({file['size']}字节)", 
                           key=f"file_{file['name']}",
                           use_container_width=True):
                    with st.spinner(f"加载 {file['name']}..."):
                        response = requests.get(file['url'], timeout=10)
                        if response.status_code == 200:
                            st.session_state.text_content = response.text
                            st.session_state.selected_file = file['path']
                            st.rerun()
    
    # 主界面
    if st.session_state.text_content:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 文本显示和统计
            st.subheader(f"📖 {st.session_state.selected_file}")
            
            text_stats = st.container()
            with text_stats:
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("字符数", len(st.session_state.text_content))
                with col_stat2:
                    chunks = text_processor.smart_chunk(
                        st.session_state.text_content, 
                        st.session_state.chunk_size
                    )
                    st.metric("分块数", len(chunks))
                with col_stat3:
                    est_time = text_processor.estimate_tts_time(st.session_state.text_content)
                    st.metric("预计时间", f"{est_time:.1f}秒")
            
            # 文本预览
            with st.expander("📝 文本预览", expanded=True):
                preview_length = min(1000, len(st.session_state.text_content))
                preview = st.session_state.text_content[:preview_length]
                if preview_length < len(st.session_state.text_content):
                    preview += "..."
                
                st.text_area(
                    "内容",
                    preview,
                    height=300,
                    disabled=True,
                    label_visibility="collapsed"
                )
            
            # 播放控制
            st.subheader("🎵 播放控制")
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("▶️ 生成并播放", type="primary", use_container_width=True):
                    if st.session_state.text_content:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # 分块生成音频
                        all_audio_files = []
                        chunks = text_processor.smart_chunk(
                            st.session_state.text_content,
                            st.session_state.chunk_size
                        )
                        
                        for i, chunk in enumerate(chunks):
                            status_text.text(f"生成第 {i+1}/{len(chunks)} 块...")
                            progress_bar.progress((i + 1) / len(chunks))
                            
                            audio_path = tts_system.text_to_speech(
                                text=chunk,
                                lang='zh-cn',
                                use_cache=st.session_state.use_cache
                            )
                            
                            if audio_path:
                                all_audio_files.append(audio_path)
                            else:
                                st.error(f"第 {i+1} 块生成失败")
                                break
                        
                        if all_audio_files:
                            # 合并音频文件
                            status_text.text("合并音频文件中...")
                            
                            try:
                                from pydub import AudioSegment
                                combined = AudioSegment.empty()
                                
                                for audio_file in all_audio_files:
                                    if os.path.exists(audio_file):
                                        audio = AudioSegment.from_mp3(audio_file)
                                        combined += audio
                                        # 添加短暂间隔
                                        combined += AudioSegment.silent(duration=100)
                                
                                # 保存合并文件
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                                    merged_path = tmp_file.name
                                
                                combined.export(merged_path, format="mp3")
                                st.session_state.audio_file = merged_path
                                
                                # 保存播放状态
                                playback_manager.update_position(
                                    st.session_state.selected_file,
                                    0,
                                    merged_path
                                )
                                
                                st.success("✅ 音频生成完成！")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"音频合并失败: {e}")
                                if all_audio_files:
                                    st.session_state.audio_file = all_audio_files[0]
                        
                        progress_bar.empty()
                        status_text.empty()
            
            with col_btn2:
                if st.button("⏸️ 保存当前位置", use_container_width=True):
                    if st.session_state.selected_file and st.session_state.audio_file:
                        # 这里可以添加实际的播放位置记录
                        current_pos = len(st.session_state.text_content) // 3
                        playback_manager.update_position(
                            st.session_state.selected_file,
                            current_pos,
                            st.session_state.audio_file
                        )
                        st.success(f"位置已保存: {current_pos}")
        
        with col2:
            # 音频播放器
            st.subheader("🎵 音频播放")
            
            if st.session_state.audio_file and os.path.exists(st.session_state.audio_file):
                try:
                    with open(st.session_state.audio_file, 'rb') as f:
                        audio_bytes = f.read()
                    
                    # 显示音频信息
                    file_size_kb = len(audio_bytes) / 1024
                    st.info(f"""
                    **音频信息**
                    - 大小: {file_size_kb:.1f} KB
                    - 引擎: {tts_system.engines.get(st.session_state.current_engine, {}).get('name', '未知')}
                    - 缓存: {'✅ 已启用' if st.session_state.use_cache else '❌ 未启用'}
                    """)
                    
                    # 播放器
                    st.audio(audio_bytes, format='audio/mp3')
                    
                    # 下载按钮
                    st.download_button(
                        label="💾 下载音频",
                        data=audio_bytes,
                        file_name=f"{st.session_state.selected_file.split('/')[-1]}.mp3",
                        mime="audio/mp3",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"加载音频失败: {e}")
            else:
                st.info("👆 点击左侧按钮生成音频")
                
                # 快速试听
                if st.button("🔊 试听片段", use_container_width=True):
                    sample = st.session_state.text_content[:200]
                    audio_path = tts_system.text_to_speech(sample, use_cache=True)
                    if audio_path:
                        st.session_state.audio_file = audio_path
                        st.rerun()
    
    else:
        # 欢迎界面
        st.info("👈 请在侧边栏选择文件来源")
        
        col_welcome1, col_welcome2 = st.columns(2)
        
        with col_welcome1:
            st.subheader("✨ 功能特色")
            st.markdown("""
            - 🚀 **多引擎支持**: gTTS、Edge TTS、pyttsx3
            - 💾 **智能缓存**: 避免重复生成，节省时间
            - ⚡ **故障转移**: 自动切换备用引擎
            - 📊 **智能分块**: 避免API限制
            - 🎯 **断点续播**: 自动保存播放位置
            - 🔄 **实时预览**: 文本和音频预览
            """)
        
        with col_welcome2:
            st.subheader("📋 使用指南")
            st.markdown("""
            1. **选择文件来源**: GitHub、本地或直接输入
            2. **配置TTS引擎**: 自动检测可用引擎
            3. **设置分块大小**: 建议400字符
            4. **启用缓存**: 提高速度
            5. **生成音频**: 点击"生成并播放"
            6. **保存位置**: 自动或手动保存
            """)
        
        # 显示可用引擎
        if st.session_state.available_engines:
            st.subheader("✅ 可用的TTS引擎")
            for engine_key in st.session_state.available_engines:
                engine_info = tts_system.engines[engine_key]
                st.caption(f"**{engine_info['name']}**: {', '.join(engine_info['languages'][:3])}...")

# ==================== 运行应用 ====================
if __name__ == "__main__":
    main()
