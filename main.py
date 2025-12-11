import streamlit as st
from gtts import gTTS
from io import BytesIO
import base64

st.set_page_config(page_title="简易TTS播放器", page_icon="🔊")

st.title("🔊 简易文字转语音播放器")
st.markdown("简单可靠的文字转语音工具，使用Google TTS引擎")

# 初始化session state
if 'audio_bytes' not in st.session_state:
    st.session_state.audio_bytes = None

# 侧边栏设置
with st.sidebar:
    st.header("设置")
    language = st.selectbox("语言", ["中文", "英文", "日语"], index=0)
    speed = st.slider("语速", 0.5, 2.0, 1.0, 0.1)
    
    # 语言代码
    lang_codes = {"中文": "zh-CN", "英文": "en", "日语": "ja"}

# 文本输入
text_input = st.text_area(
    "输入要转换的文本",
    height=200,
    placeholder="在此输入文本...",
    help="建议不超过1000字符"
)

col1, col2 = st.columns(2)
with col1:
    convert_btn = st.button("🔊 转换为语音", type="primary", use_container_width=True)
with col2:
    clear_btn = st.button("🗑️ 清除", use_container_width=True)

if clear_btn:
    st.session_state.audio_bytes = None
    st.rerun()

# 转换逻辑
if convert_btn and text_input.strip():
    with st.spinner("正在生成语音..."):
        try:
            # 使用gTTS
            tts = gTTS(
                text=text_input,
                lang=lang_codes[language],
                slow=(speed < 1.0)
            )
            
            # 保存到内存
            audio_bytes = BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            
            # 保存到session state
            st.session_state.audio_bytes = audio_bytes.read()
            
            st.success("✅ 语音生成成功！")
            
        except Exception as e:
            st.error(f"转换失败: {str(e)}")
            st.info("请检查网络连接或尝试减少文本长度")

# 显示音频播放器
if st.session_state.audio_bytes:
    st.markdown("### 🎵 播放音频")
    
    # 方法1：直接使用st.audio
    st.audio(st.session_state.audio_bytes, format="audio/mp3")
    
    # 方法2：使用HTML audio标签（备用）
    st.markdown("### 备用播放器（如果上面无法播放）")
    
    # 转换为base64
    b64 = base64.b64encode(st.session_state.audio_bytes).decode()
    audio_html = f"""
    <audio controls autoplay style="width: 100%">
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        您的浏览器不支持音频播放
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)
    
    # 下载链接
    st.markdown("### 💾 下载音频")
    href = f'<a href="data:audio/mp3;base64,{b64}" download="speech.mp3">点击下载MP3文件</a>'
    st.markdown(href, unsafe_allow_html=True)
    
    # 音频信息
    audio_size = len(st.session_state.audio_bytes) / 1024
    st.info(f"音频大小: {audio_size:.1f} KB | 格式: MP3")

# 使用说明
with st.expander("使用说明"):
    st.markdown("""
    1. 在文本框中输入文字
    2. 选择语言和语速
    3. 点击"转换为语音"按钮
    4. 播放或下载生成的音频
    
    **注意**：
    - 文本建议不超过1000字符
    - 需要网络连接（使用Google TTS）
    - 如果无法播放，请尝试备用播放器
    """)

st.markdown("---")
st.caption("简易文字转语音播放器 | 使用Google TTS")
