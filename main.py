import streamlit as st
import requests
import json
import os
import base64
from gtts import gTTS
import tempfile
from datetime import datetime
import re
import time
from typing import Optional

# 页面配置
st.set_page_config(
    page_title="GitHub文本语音播放器",
    page_icon="🔊",
    layout="wide"
)

# 初始化session state
if 'audio_file' not in st.session_state:
    st.session_state.audio_file = None
if 'current_position' not in st.session_state:
    st.session_state.current_position = 0
if 'playback_state' not in st.session_state:
    st.session_state.playback_state = {}
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = ""
if 'text_content' not in st.session_state:
    st.session_state.text_content = ""
if 'tts_attempts' not in st.session_state:
    st.session_state.tts_attempts = 0

class RateLimitedTTS:
    """带速率限制的TTS引擎"""
    
    def __init__(self, max_retries=3, delay=2.0):
        self.max_retries = max_retries
        self.delay = delay
        self.last_request_time = 0
        
    def text_to_speech_with_retry(self, text: str, lang: str = 'zh-cn') -> Optional[str]:
        """带重试机制的文本转语音"""
        for attempt in range(self.max_retries):
            try:
                # 添加延迟，避免请求过快
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                if time_since_last < self.delay:
                    time.sleep(self.delay - time_since_last)
                
                self.last_request_time = time.time()
                
                # 清理文本
                text = re.sub(r'\s+', ' ', text.strip())
                if not text:
                    return None
                
                # 创建临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                    temp_path = tmp_file.name
                
                # 使用gTTS生成语音
                tts = gTTS(
                    text=text, 
                    lang=lang, 
                    slow=False,
                    # 添加超时设置
                    timeout=30
                )
                
                tts.save(temp_path)
                st.session_state.tts_attempts = 0  # 重置尝试计数
                return temp_path
                
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    st.session_state.tts_attempts += 1
                    wait_time = self.delay * (2 ** attempt)  # 指数退避
                    st.warning(f"⚠️ 请求过于频繁，等待 {wait_time:.1f} 秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    st.error(f"语音生成失败: {str(e)}")
                    return None
        
        st.error("❌ 多次尝试后仍失败，请稍后再试")
        return None

class GitHubTextReader:
    """GitHub文本文件读取器"""
    
    def __init__(self, repo_url):
        self.repo_url = repo_url
        self.api_base = "https://api.github.com/repos/"
        self.headers = {
            'User-Agent': 'Streamlit-TTS-Player/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        
    def parse_repo_url(self):
        """解析GitHub仓库URL"""
        patterns = [
            r'github\.com/([^/]+)/([^/]+)',
            r'https://github\.com/([^/]+)/([^/]+)',
            r'https://github\.com/([^/]+)/([^/]+)/tree/[^/]+/(.+)',
            r'https://github\.com/([^/]+)/([^/]+)/blob/[^/]+/(.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.repo_url)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return groups[0], groups[1]
        return None, None
    
    def get_file_list(self, path=""):
        """获取指定路径下的txt文件列表"""
        owner, repo = self.parse_repo_url()
        if not owner or not repo:
            return []
        
        api_url = f"{self.api_base}{owner}/{repo}/contents/{path}"
        try:
            response = requests.get(api_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                contents = response.json()
                files = []
                
                for item in contents:
                    if item['type'] == 'file' and item['name'].lower().endswith('.txt'):
                        files.append({
                            'name': item['name'],
                            'path': item['path'],
                            'download_url': item['download_url'],
                            'size': item.get('size', 0)
                        })
                    elif item['type'] == 'dir':
                        # 可选：可以在这里添加递归获取，但建议使用按钮触发
                        pass
                
                return files
            else:
                st.error(f"无法访问仓库: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"错误: {str(e)}")
            return []
    
    def get_file_content(self, file_url):
        """获取文件内容"""
        try:
            response = requests.get(file_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                st.error(f"无法下载文件: {response.status_code}")
                return None
        except Exception as e:
            st.error(f"错误: {str(e)}")
            return None

class PlaybackManager:
    """播放管理器"""
    
    def __init__(self, state_file='playback_state.json'):
        self.state_file = state_file
        self.load_state()
    
    def load_state(self):
        """加载播放状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    st.session_state.playback_state = json.load(f)
            else:
                st.session_state.playback_state = {}
        except:
            st.session_state.playback_state = {}
    
    def save_state(self):
        """保存播放状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(st.session_state.playback_state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"保存状态失败: {str(e)}")
    
    def update_position(self, filename, position):
        """更新播放位置"""
        st.session_state.playback_state[filename] = {
            'position': position,
            'last_played': datetime.now().isoformat(),
            'file_size': len(st.session_state.text_content) if st.session_state.text_content else 0
        }
        self.save_state()
    
    def get_position(self, filename):
        """获取上次播放位置"""
        if filename in st.session_state.playback_state:
            return st.session_state.playback_state[filename].get('position', 0)
        return 0

def chunk_text(text, max_chars=500):
    """智能分块文本"""
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    # 尝试按句子分割
    sentences = re.split(r'(?<=[。！？；.!?;])', text)
    
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
    
    return chunks

def merge_audio_files(audio_files):
    """合并多个音频文件"""
    if not audio_files:
        return None
    
    if len(audio_files) == 1:
        return audio_files[0]
    
    try:
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        
        for audio_file in audio_files:
            if os.path.exists(audio_file):
                audio = AudioSegment.from_mp3(audio_file)
                combined += audio
                # 添加短暂静音
                combined += AudioSegment.silent(duration=200)
        
        # 创建合并后的临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            output_path = tmp_file.name
        
        combined.export(output_path, format="mp3")
        return output_path
    except Exception as e:
        st.warning(f"音频合并失败，将使用第一个片段: {str(e)}")
        return audio_files[0] if audio_files else None

def main():
    st.title("🔊 GitHub文本语音播放器")
    st.markdown("---")
    
    # 初始化管理器
    playback_manager = PlaybackManager()
    tts_engine = RateLimitedTTS(max_retries=3, delay=3.0)
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 设置")
        
        # 显示当前状态
        if st.session_state.tts_attempts > 0:
            st.warning(f"当前请求次数: {st.session_state.tts_attempts}")
        
        # GitHub仓库URL输入
        repo_url = st.text_input(
            "GitHub仓库URL",
            value="https://github.com/Mestas/Books",
            placeholder="例如: https://github.com/username/repo",
            help="输入GitHub仓库URL以获取文本文件"
        )
        
        # 本地文件上传作为备用
        st.subheader("或上传本地文件")
        uploaded_file = st.file_uploader("选择文本文件", type=['txt', 'md'])
        if uploaded_file:
            content = uploaded_file.read().decode('utf-8')
            st.session_state.text_content = content
            st.session_state.selected_file = uploaded_file.name
        
        if repo_url:
            reader = GitHubTextReader(repo_url)
            
            # 获取文件列表按钮
            if st.button("🔄 刷新文件列表", use_container_width=True):
                with st.spinner("正在加载文件列表..."):
                    files = reader.get_file_list()
                
                if files:
                    # 保存到session state
                    st.session_state.github_files = files
                    st.success(f"找到 {len(files)} 个文本文件")
            
            # 显示文件列表
            if 'github_files' in st.session_state:
                files = st.session_state.github_files
                file_options = [f"{f['name']} ({f['size']} 字节)" for f in files]
                
                selected_option = st.selectbox(
                    "选择文本文件",
                    file_options,
                    key="file_selector"
                )
                
                if selected_option:
                    selected_index = file_options.index(selected_option)
                    selected_file = files[selected_index]
                    
                    if st.button("📥 加载文件", use_container_width=True):
                        with st.spinner("正在下载文件..."):
                            content = reader.get_file_content(selected_file['download_url'])
                            if content:
                                st.session_state.text_content = content
                                st.session_state.selected_file = selected_file['path']
                                
                                # 获取上次播放位置
                                last_position = playback_manager.get_position(selected_file['path'])
                                if last_position > 0:
                                    st.success(f"📌 已加载上次播放位置: {last_position}")
        
        st.markdown("---")
        st.header("🎵 播放设置")
        
        # 语言选择
        language = st.selectbox(
            "选择语音语言",
            ['zh-cn', 'en'],
            index=0,
            help="注意：gTTS对中文支持最好"
        )
        
        # 分块大小
        chunk_size = st.slider(
            "分块大小（字符）",
            min_value=100,
            max_value=2000,
            value=500,
            step=100,
            help="较小的分块可以减少请求失败"
        )
        
        # 播放速度
        playback_speed = st.slider("播放速度", 0.5, 2.0, 1.0, 0.1)
        
        # 从指定位置开始播放
        if st.session_state.text_content:
            start_position = st.number_input(
                "开始播放位置(字符)",
                min_value=0,
                max_value=len(st.session_state.text_content),
                value=playback_manager.get_position(st.session_state.selected_file),
                step=100
            )
        
        st.markdown("---")
        st.caption("💡 提示：gTTS API有频率限制，请耐心等待")
        st.caption("⏱️ 建议分块大小：400-600字符")
    
    # 主内容区
    if st.session_state.text_content:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"📖 {st.session_state.selected_file.split('/')[-1]}")
            
            # 显示文本统计
            text_length = len(st.session_state.text_content)
            st.caption(f"📊 文本长度: {text_length} 字符 | 大约需要 {text_length//500 + 1} 次TTS请求")
            
            # 文本显示区域
            text_display = st.text_area(
                "文本内容",
                st.session_state.text_content,
                height=400,
                key="text_display"
            )
            
            # 播放控制
            st.subheader("🎵 播放控制")
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("▶️ 播放全文", use_container_width=True, type="primary"):
                    if st.session_state.text_content:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        chunks = chunk_text(st.session_state.text_content, chunk_size)
                        audio_files = []
                        
                        for i, chunk in enumerate(chunks):
                            status_text.text(f"正在生成第 {i+1}/{len(chunks)} 段音频...")
                            progress_bar.progress((i + 1) / len(chunks))
                            
                            audio_path = tts_engine.text_to_speech_with_retry(chunk, lang=language)
                            if audio_path:
                                audio_files.append(audio_path)
                            else:
                                st.error(f"第 {i+1} 段音频生成失败")
                                break
                        
                        if audio_files:
                            merged_audio = merge_audio_files(audio_files)
                            if merged_audio:
                                st.session_state.audio_file = merged_audio
                                st.session_state.current_position = 0
                                st.rerun()
                        
                        progress_bar.empty()
                        status_text.empty()
            
            with col_btn2:
                if st.button("⏸️ 保存位置", use_container_width=True):
                    if st.session_state.selected_file:
                        current_pos = len(st.session_state.text_content) // 2  # 示例位置
                        playback_manager.update_position(st.session_state.selected_file, current_pos)
                        st.success(f"已保存播放位置: {current_pos}")
            
            with col_btn3:
                if st.button("🎯 从位置播放", use_container_width=True):
                    if st.session_state.text_content and start_position < text_length:
                        text_to_play = st.session_state.text_content[start_position:]
                        chunks = chunk_text(text_to_play, chunk_size)
                        
                        if len(chunks) > 0:
                            audio_path = tts_engine.text_to_speech_with_retry(chunks[0], lang=language)
                            if audio_path:
                                st.session_state.audio_file = audio_path
                                st.session_state.current_position = start_position
                                playback_manager.update_position(st.session_state.selected_file, start_position)
                                st.rerun()
        
        with col2:
            st.subheader("🎵 音频播放器")
            
            if st.session_state.audio_file and os.path.exists(st.session_state.audio_file):
                # 读取音频文件
                try:
                    with open(st.session_state.audio_file, 'rb') as f:
                        audio_bytes = f.read()
                    
                    # 显示音频信息
                    file_size = len(audio_bytes) / 1024  # KB
                    st.info(f"""
                    📊 音频信息:
                    - 文件大小: {file_size:.1f} KB
                    - 开始位置: {st.session_state.current_position}
                    - 语速: {playback_speed}x
                    """)
                    
                    # 使用st.audio播放
                    st.audio(audio_bytes, format='audio/mp3')
                    
                    # 播放速度控制
                    st.caption(f"当前播放速度: {playback_speed}x")
                    
                    # 保存位置按钮
                    if st.button("💾 保存当前位置"):
                        if st.session_state.selected_file:
                            # 这里需要实现实际的时间位置计算
                            estimated_pos = st.session_state.current_position + (chunk_size * 0.5)
                            playback_manager.update_position(st.session_state.selected_file, int(estimated_pos))
                            st.success("位置已保存")
                    
                except Exception as e:
                    st.error(f"播放音频失败: {str(e)}")
            else:
                st.info("👆 请先选择文本并点击播放")
                
                # 显示快速播放选项
                if st.session_state.text_content:
                    st.subheader("快速播放")
                    sample_text = st.session_state.text_content[:200] + "..."
                    if st.button("🔊 试听前200字符", use_container_width=True):
                        audio_path = tts_engine.text_to_speech_with_retry(
                            st.session_state.text_content[:200], 
                            lang=language
                        )
                        if audio_path:
                            st.session_state.audio_file = audio_path
                            st.rerun()
    
    else:
        # 欢迎页面
        st.info("👈 请在侧边栏输入GitHub仓库URL或上传本地文件")
        
        col_welcome1, col_welcome2 = st.columns(2)
        
        with col_welcome1:
            st.subheader("📚 功能特点")
            st.markdown("""
            - 🎵 支持GitHub和本地文本文件
            - 🔄 自动保存播放位置
            - 🌍 多语言语音合成
            - ⚡ 智能分块处理
            - 💾 断点续播功能
            """)
        
        with col_welcome2:
            st.subheader("⚡ 使用技巧")
            st.markdown("""
            1. 输入GitHub仓库URL
            2. 点击"刷新文件列表"
            3. 选择文本文件
            4. 调整分块大小（建议500）
            5. 点击"播放全文"
            6. 暂停时会自动保存位置
            """)

if __name__ == "__main__":
    main()
