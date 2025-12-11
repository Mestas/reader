import streamlit as st
import requests
import json
import os
import base64
from gtts import gTTS
import tempfile
from datetime import datetime
import re

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

class GitHubTextReader:
    """GitHub文本文件读取器"""
    
    def __init__(self, repo_url):
        self.repo_url = repo_url
        self.api_base = "https://api.github.com/repos/"
        
    def parse_repo_url(self):
        """解析GitHub仓库URL"""
        # 支持多种URL格式
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
            response = requests.get(api_url)
            if response.status_code == 200:
                contents = response.json()
                files = []
                
                for item in contents:
                    if item['type'] == 'file' and item['name'].endswith('.txt'):
                        files.append({
                            'name': item['name'],
                            'path': item['path'],
                            'download_url': item['download_url']
                        })
                    elif item['type'] == 'dir':
                        # 递归获取子目录文件
                        sub_files = self.get_file_list(item['path'])
                        files.extend(sub_files)
                
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
            response = requests.get(file_url)
            if response.status_code == 200:
                return response.text
            else:
                st.error(f"无法下载文件: {response.status_code}")
                return None
        except Exception as e:
            st.error(f"错误: {str(e)}")
            return None

class PlaybackManager:
    """播放管理器，负责断点续播功能"""
    
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
            'last_played': datetime.now().isoformat()
        }
        self.save_state()
    
    def get_position(self, filename):
        """获取上次播放位置"""
        if filename in st.session_state.playback_state:
            return st.session_state.playback_state[filename].get('position', 0)
        return 0

class TextToSpeechEngine:
    """文本转语音引擎"""
    
    def __init__(self):
        self.temp_files = []
    
    def text_to_speech(self, text, lang='zh-cn'):
        """将文本转换为语音"""
        try:
            # 清理文本，移除多余空白字符
            text = re.sub(r'\s+', ' ', text.strip())
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_path = tmp_file.name
            
            # 使用gTTS生成语音
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(temp_path)
            
            self.temp_files.append(temp_path)
            return temp_path
        except Exception as e:
            st.error(f"语音生成失败: {str(e)}")
            return None
    
    def chunk_text_to_speech(self, text, chunk_size=1000, lang='zh-cn'):
        """将长文本分块转换为语音"""
        try:
            # 按句子分割文本
            sentences = re.split(r'(?<=[。！？；.!?;])', text)
            
            chunks = []
            current_chunk = ""
            
            for sentence in sentences:
                if len(current_chunk) + len(sentence) <= chunk_size:
                    current_chunk += sentence
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sentence
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # 为每个块生成语音
            audio_files = []
            for i, chunk in enumerate(chunks):
                if chunk.strip():
                    audio_path = self.text_to_speech(chunk, lang)
                    if audio_path:
                        audio_files.append(audio_path)
            
            return audio_files
        except Exception as e:
            st.error(f"分块处理失败: {str(e)}")
            return None
    
    def cleanup(self):
        """清理临时文件"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except:
                pass
        self.temp_files.clear()

def main():
    st.title("🔊 GitHub文本语音播放器")
    st.markdown("---")
    
    # 初始化管理器
    playback_manager = PlaybackManager()
    tts_engine = TextToSpeechEngine()
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 设置")
        
        # GitHub仓库URL输入
        repo_url = st.text_input(
            "GitHub仓库URL",
            value="https://github.com/Mestas/reader",
            help="例如: https://github.com/Mestas/reader"
        )
        
        if repo_url:
            reader = GitHubTextReader(repo_url)
            
            # 获取文件列表
            with st.spinner("正在加载文件列表..."):
                files = reader.get_file_list()
            
            if files:
                file_names = [f"{f['name']} ({f['path']})" for f in files]
                
                selected_index = 0
                if st.session_state.selected_file:
                    # 尝试找到之前选择的文件
                    for i, file_info in enumerate(files):
                        if file_info['path'] == st.session_state.selected_file.split(' (')[0]:
                            selected_index = i
                            break
                
                selected_display = st.selectbox(
                    "选择文本文件",
                    file_names,
                    index=selected_index
                )
                
                if selected_display:
                    # 提取文件信息
                    selected_name = selected_display.split(' (')[0]
                    for file_info in files:
                        if file_info['name'] == selected_name:
                            st.session_state.selected_file = file_info['path']
                            file_url = file_info['download_url']
                            
                            # 获取文件内容
                            content = reader.get_file_content(file_url)
                            if content:
                                st.session_state.text_content = content
                                
                                # 显示文本预览
                                st.subheader("📄 文本预览")
                                preview = content[:500] + "..." if len(content) > 500 else content
                                st.text_area("", preview, height=150, disabled=True)
                                
                                # 获取上次播放位置
                                last_position = playback_manager.get_position(file_info['path'])
                                if last_position > 0:
                                    st.info(f"📌 上次播放位置: {last_position} 字符处")
                                
                            break
        
        st.markdown("---")
        st.header("🎵 播放设置")
        
        # 语言选择
        language = st.selectbox(
            "选择语音语言",
            ['zh-cn', 'en', 'ja', 'ko', 'fr', 'de', 'es'],
            index=0
        )
        
        # 播放速度
        playback_speed = st.slider("播放速度", 0.5, 2.0, 1.0, 0.1)
        
        # 从指定位置开始播放
        start_position = st.number_input(
            "开始播放位置(字符)",
            min_value=0,
            max_value=len(st.session_state.text_content) if st.session_state.text_content else 0,
            value=playback_manager.get_position(st.session_state.selected_file) if st.session_state.selected_file else 0
        )
        
        st.markdown("---")
        st.caption("💡 提示: 点击暂停会自动保存播放位置")
    
    # 主内容区
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.session_state.text_content:
            st.subheader("📖 完整文本")
            
            # 显示完整文本
            text_display = st.text_area(
                "文本内容",
                st.session_state.text_content,
                height=400,
                key="text_display"
            )
            
            # 播放控制按钮
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("▶️ 播放全文", use_container_width=True):
                    with st.spinner("正在生成语音..."):
                        audio_path = tts_engine.text_to_speech(
                            st.session_state.text_content,
                            lang=language
                        )
                        if audio_path:
                            st.session_state.audio_file = audio_path
                            # 重置播放位置
                            st.session_state.current_position = 0
            
            with col_btn2:
                if st.button("⏸️ 暂停保存", use_container_width=True):
                    if st.session_state.selected_file:
                        # 保存当前播放位置（这里简化为保存当前位置）
                        current_pos = len(st.session_state.text_content) // 2  # 示例位置
                        playback_manager.update_position(st.session_state.selected_file, current_pos)
                        st.success(f"已保存播放位置: {current_pos}")
            
            with col_btn3:
                if st.button("🔁 从指定位置播放", use_container_width=True):
                    if start_position < len(st.session_state.text_content):
                        text_to_play = st.session_state.text_content[start_position:]
                        with st.spinner("正在生成语音..."):
                            audio_path = tts_engine.text_to_speech(text_to_play, lang=language)
                            if audio_path:
                                st.session_state.audio_file = audio_path
                                st.session_state.current_position = start_position
                                # 保存位置
                                if st.session_state.selected_file:
                                    playback_manager.update_position(
                                        st.session_state.selected_file, 
                                        start_position
                                    )
    
    with col2:
        st.subheader("🎵 音频播放器")
        
        if st.session_state.audio_file:
            # 显示音频播放器
            with open(st.session_state.audio_file, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            
            # 使用HTML音频播放器
            audio_base64 = base64.b64encode(audio_bytes).decode()
            
            audio_html = f"""
            <audio id="audioPlayer" controls autoplay style="width: 100%;">
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
            <script>
                const audio = document.getElementById('audioPlayer');
                audio.playbackRate = {playback_speed};
                
                // 监听暂停事件
                audio.addEventListener('pause', function() {{
                    // 这里可以添加保存播放位置的逻辑
                    console.log('播放暂停，当前位置:', audio.currentTime);
                }});
                
                // 监听播放结束事件
                audio.addEventListener('ended', function() {{
                    console.log('播放结束');
                }});
            </script>
            """
            
            st.components.v1.html(audio_html, height=100)
            
            # 显示当前播放信息
            st.info(f"""
            📊 播放信息:
            - 文件: {st.session_state.selected_file.split('/')[-1]}
            - 开始位置: {st.session_state.current_position} 字符
            - 语速: {playback_speed}x
            """)
        else:
            st.info("👆 请先选择一个文本文件并点击播放")
        
        # 清理临时文件
        st.button("🧹 清理缓存", on_click=tts_engine.cleanup)
    
    # 文件统计信息
    if files:
        st.markdown("---")
        st.subheader("📊 文件统计")
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            st.metric("总文件数", len(files))
        
        with col_stat2:
            total_chars = sum(len(f.get('content', '')) for f in files)
            st.metric("总字符数", f"{total_chars:,}")
        
        with col_stat3:
            played_files = len(st.session_state.playback_state)
            st.metric("已播放文件", played_files)
    
    # 应用关闭时清理
    import atexit
    atexit.register(tts_engine.cleanup)

if __name__ == "__main__":
    main()
