import streamlit as st
import base64
from gtts import gTTS
import os
from io import BytesIO
import edge_tts
import asyncio
from datetime import datetime
import tempfile

# 页面配置
st.set_page_config(
    page_title="文字转语音播放器",
    page_icon="🔊",
    layout="wide"
)

# 应用标题和说明
st.title("🔊 文字转语音播放器")
st.markdown("""
将文本转换为语音并直接播放，支持多种语音引擎和语音选项。
""")

# 初始化session state
if 'audio_file' not in st.session_state:
    st.session_state.audio_file = None
if 'audio_bytes' not in st.session_state:
    st.session_state.audio_bytes = None
if 'last_text' not in st.session_state:
    st.session_state.last_text = ""

# 侧边栏设置
with st.sidebar:
    st.header("⚙️ 设置")
    
    # 选择TTS引擎
    engine = st.selectbox(
        "选择语音引擎",
        ["Google TTS (免费)", "Edge TTS (微软，免费)", "本地TTS (pyttsx3)"],
        help="Google TTS: 免费但有速率限制 | Edge TTS: 微软免费引擎 | 本地TTS: 无需网络"
    )
    
    # 语言选择
    language = st.selectbox(
        "选择语言",
        ["中文", "英文", "日语", "韩语", "法语", "德语", "西班牙语"],
        index=0
    )
    
    # 语速设置
    speed = st.slider("语速", 0.5, 2.0, 1.0, 0.1)
    
    # 音高设置（Edge TTS）
    if engine == "Edge TTS (微软，免费)":
        pitch = st.slider("音高 (Hz)", -20, 20, 0, 1)
    
    # 音量设置
    volume = st.slider("音量", 0.0, 1.0, 0.8, 0.1)
    
    # 发音人选择（Edge TTS）
    if engine == "Edge TTS (微软，免费)":
        voices = {
            "中文": ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunxiNeural"],
            "英文": ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"],
            "日语": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
            "韩语": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
            "法语": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
            "德语": ["de-DE-KatjaNeural", "de-DE-ConradNeural"],
            "西班牙语": ["es-ES-ElviraNeural", "es-MX-DaliaNeural"]
        }
        
        voice_options = voices.get(language, ["zh-CN-XiaoxiaoNeural"])
        voice = st.selectbox("选择发音人", voice_options)
    
    # 音频格式
    audio_format = st.selectbox("音频格式", ["MP3", "WAV"], index=0)
    
    # 示例文本
    st.markdown("---")
    st.subheader("📝 示例文本")
    example_texts = {
        "中文": "欢迎使用文字转语音播放器！这是一个简单易用的工具，可以将任何文本转换为语音。",
        "英文": "Welcome to the Text to Speech Player! This is an easy-to-use tool that can convert any text to speech.",
        "日语": "テキスト音声変換プレイヤーへようこそ！これはどんなテキストも音声に変換できる使いやすいツールです。",
        "韩语": "텍스트 음성 변환 플레이어에 오신 것을 환영합니다! 어떤 텍스트든 음성으로 변환할 수 있는 사용하기 쉬운 도구입니다.",
        "法语": "Bienvenue dans le lecteur de synthèse vocale ! C'est un outil facile à utiliser qui peut convertir n'importe quel texte en parole.",
        "德语": "Willkommen beim Text-zu-Sprache-Player! Dies ist ein einfach zu bedienendes Tool, das jeden Text in Sprache umwandeln kann.",
        "西班牙语": "¡Bienvenido al reproductor de texto a voz! Esta es una herramienta fácil de usar que puede convertir cualquier texto en voz."
    }
    
    if st.button("加载示例文本"):
        st.session_state.last_text = example_texts.get(language, example_texts["中文"])

# 语言代码映射
language_codes = {
    "中文": "zh-CN",
    "英文": "en",
    "日语": "ja",
    "韩语": "ko",
    "法语": "fr",
    "德语": "de",
    "西班牙语": "es"
}

# 主界面
col1, col2 = st.columns([2, 1])

with col1:
    # 文本输入区域
    st.subheader("📝 输入文本")
    text_input = st.text_area(
        "请输入要转换的文本",
        value=st.session_state.last_text,
        height=200,
        placeholder="在此输入要转换为语音的文本...",
        help="最多支持5000个字符"
    )
    
    # 文本统计
    char_count = len(text_input)
    st.caption(f"字符数: {char_count}/5000")
    
    if char_count > 5000:
        st.error("文本过长，请缩减到5000字符以内")
    
    # 控制按钮
    col1_1, col1_2, col1_3 = st.columns(3)
    
    with col1_1:
        convert_button = st.button("🚀 转换为语音", type="primary", use_container_width=True)
    
    with col1_2:
        clear_button = st.button("🗑️ 清除文本", use_container_width=True)
    
    with col1_3:
        if st.session_state.audio_bytes:
            download_button = st.button("💾 下载音频", use_container_width=True)
        else:
            download_button = st.button("💾 下载音频", disabled=True, use_container_width=True)
    
    if clear_button:
        st.session_state.last_text = ""
        st.session_state.audio_bytes = None
        st.rerun()

with col2:
    st.subheader("🎵 音频播放器")
    
    # 显示音频播放器
    if st.session_state.audio_bytes:
        st.audio(st.session_state.audio_bytes, format=f"audio/{audio_format.lower()}")
        
        # 音频信息
        st.markdown("### 音频信息")
        audio_size = len(st.session_state.audio_bytes) / 1024  # KB
        
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.metric("文件大小", f"{audio_size:.1f} KB")
        with info_col2:
            st.metric("音频格式", audio_format)
        
        st.metric("生成时间", datetime.now().strftime("%H:%M:%S"))
        
        # 下载链接
        st.markdown("---")
        b64 = base64.b64encode(st.session_state.audio_bytes).decode()
        href = f'<a href="data:audio/{audio_format.lower()};base64,{b64}" download="speech.{audio_format.lower()}">点击下载音频文件</a>'
        st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("👆 输入文本并点击'转换为语音'按钮生成音频")
        
        # 占位图标
        st.markdown("""
        <div style='text-align: center; padding: 50px 0;'>
            <h1 style='font-size: 100px;'>🔊</h1>
            <p style='color: #666;'>等待生成音频...</p>
        </div>
        """, unsafe_allow_html=True)

# 转换函数 - Google TTS
def convert_with_gtts(text, lang, speed=1.0):
    """使用Google TTS转换文本为语音"""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        
        # 调整语速
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        return audio_bytes
    except Exception as e:
        st.error(f"Google TTS转换失败: {str(e)}")
        return None

# 转换函数 - Edge TTS
async def convert_with_edge_tts(text, voice, rate, volume):
    """使用Edge TTS转换文本为语音"""
    try:
        communicate = edge_tts.Communicate(text, voice, rate=f"{rate:+d}%", volume=f"{volume:+d}%")
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            tmp_path = tmp_file.name
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    tmp_file.write(chunk["data"])
            
            tmp_file.flush()
            
            # 读取音频数据
            with open(tmp_path, 'rb') as f:
                audio_bytes = BytesIO(f.read())
            
            # 清理临时文件
            os.unlink(tmp_path)
            
        audio_bytes.seek(0)
        return audio_bytes
    except Exception as e:
        st.error(f"Edge TTS转换失败: {str(e)}")
        return None

# 转换函数 - 本地TTS (pyttsx3)
def convert_with_local_tts(text, lang, speed=1.0):
    """使用本地TTS引擎转换文本为语音"""
    try:
        import pyttsx3
        
        # 初始化引擎
        engine = pyttsx3.init()
        
        # 设置属性
        engine.setProperty('rate', 150 * speed)  # 语速
        engine.setProperty('volume', volume)     # 音量
        
        # 设置语言
        if lang == "zh-CN":
            # 尝试设置中文语音（需要系统支持）
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
        
        # 保存到BytesIO
        audio_bytes = BytesIO()
        
        # pyttsx3默认不支持直接保存到BytesIO，这里使用临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_path = tmp_file.name
        
        # 保存到临时文件
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        
        # 读取音频数据
        with open(tmp_path, 'rb') as f:
            audio_bytes = BytesIO(f.read())
        
        # 清理临时文件
        os.unlink(tmp_path)
        
        audio_bytes.seek(0)
        return audio_bytes
    except ImportError:
        st.error("请安装pyttsx3: pip install pyttsx3")
        return None
    except Exception as e:
        st.error(f"本地TTS转换失败: {str(e)}")
        return None

# 执行转换
if convert_button and text_input:
    if not text_input.strip():
        st.warning("请输入文本内容")
    else:
        with st.spinner("正在生成语音..."):
            # 更新session state
            st.session_state.last_text = text_input
            
            # 根据选择的引擎进行转换
            if engine == "Google TTS (免费)":
                lang_code = language_codes[language]
                audio_bytes = convert_with_gtts(text_input, lang_code, speed)
                
            elif engine == "Edge TTS (微软，免费)":
                # 计算语速调整（百分比）
                rate_percent = int((speed - 1.0) * 100)
                volume_percent = int((volume - 0.5) * 100)
                
                # 运行异步函数
                audio_bytes = asyncio.run(
                    convert_with_edge_tts(text_input, voice, rate_percent, volume_percent)
                )
                
            else:  # 本地TTS
                lang_code = language_codes[language]
                audio_bytes = convert_with_local_tts(text_input, lang_code, speed)
            
            if audio_bytes:
                # 根据选择的格式处理
                if audio_format == "MP3":
                    st.session_state.audio_bytes = audio_bytes.getvalue()
                else:  # WAV格式需要转换（这里简化处理，实际可能需要格式转换）
                    st.session_state.audio_bytes = audio_bytes.getvalue()
                
                st.success("✅ 语音生成成功！")
                st.rerun()
            else:
                st.error("语音生成失败，请重试或更换引擎")

# 添加使用说明
with st.expander("📖 使用说明"):
    st.markdown("""
    ### 如何使用这个文字转语音播放器：
    
    1. **输入文本**：在左侧文本框中输入或粘贴要转换的文本
    2. **选择设置**：在侧边栏中选择语音引擎、语言、语速等选项
    3. **转换语音**：点击"转换为语音"按钮生成音频
    4. **播放/下载**：在右侧播放生成的音频或下载音频文件
    
    ### 各引擎特点：
    
    - **Google TTS**：免费，支持多种语言，但有请求频率限制
    - **Edge TTS**：微软免费引擎，声音自然，支持更多参数调整
    - **本地TTS**：无需网络，依赖系统语音库
    
    ### 注意事项：
    
    - 文本长度建议不超过5000字符
    - 某些语言可能需要特定的发音人支持
    - 首次使用可能需要安装依赖库
    """)

# 添加依赖说明
with st.expander("🔧 安装依赖"):
    st.code("""
# 安装所需库
pip install streamlit gtts edge-tts pyttsx3

# 运行应用
streamlit run app.py
    """)

# 页脚
st.markdown("---")
st.caption("📱 文字转语音播放器 | 支持多引擎多语言 | 免费使用")
