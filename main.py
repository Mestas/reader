import streamlit as st
import base64
from gtts import gTTS
import os
from io import BytesIO
import edge_tts
import asyncio
from datetime import datetime
import tempfile
import time
import random

# 页面配置
st.set_page_config(
    page_title="文字转语音播放器",
    page_icon="🔊",
    layout="wide"
)

# 应用标题和说明
st.title("🔊 文字转语音播放器")
st.markdown("将文本转换为语音并直接播放，支持多种语音引擎和音色选择。")

# 初始化session state
if 'audio_data' not in st.session_state:
    st.session_state.audio_data = None
if 'audio_format' not in st.session_state:
    st.session_state.audio_format = "mp3"
if 'audio_generated' not in st.session_state:
    st.session_state.audio_generated = False
if 'input_text' not in st.session_state:
    st.session_state.input_text = ""
if 'selected_voice' not in st.session_state:
    st.session_state.selected_voice = "zh-CN-XiaoxiaoNeural"

# 语音数据库（Edge TTS）
VOICE_DATABASE = {
    "中文": {
        "女声": [
            {"name": "晓晓 (年轻女声)", "id": "zh-CN-XiaoxiaoNeural", "style": "活泼", "description": "年轻、自然的女声，适合大部分场景"},
            {"name": "晓伊 (温柔女声)", "id": "zh-CN-XiaoyiNeural", "style": "温柔", "description": "温柔、细腻的女声，适合讲述故事"},
            {"name": "云希 (男声)", "id": "zh-CN-YunxiNeural", "style": "稳重", "description": "成熟、稳重的男声，适合正式场合"},
            {"name": "云燕 (女声)", "id": "zh-CN-YunyanNeural", "style": "专业", "description": "专业、清晰的女声，适合播报新闻"},
            {"name": "晓晨 (女声)", "id": "zh-CN-XiaochenNeural", "style": "亲切", "description": "亲切、友好的女声，适合客服场景"},
            {"name": "晓涵 (女声)", "id": "zh-CN-XiaohanNeural", "style": "活泼", "description": "活泼、开朗的女声"},
            {"name": "晓墨 (男声)", "id": "zh-CN-XiaomoNeural", "style": "磁性", "description": "富有磁性的男声"},
            {"name": "晓睿 (女声)", "id": "zh-CN-XiaoruiNeural", "style": "温柔", "description": "温柔、细腻的女声"},
            {"name": "晓双 (女声)", "id": "zh-CN-XiaoshuangNeural", "style": "可爱", "description": "可爱、俏皮的女声"},
        ],
        "男声": [
            {"name": "云希 (男声)", "id": "zh-CN-YunxiNeural", "style": "稳重", "description": "成熟、稳重的男声"},
            {"name": "晓墨 (男声)", "id": "zh-CN-XiaomoNeural", "style": "磁性", "description": "富有磁性的男声"},
            {"name": "云扬 (男声)", "id": "zh-CN-YunyangNeural", "style": "专业", "description": "专业、清晰的男声"},
        ]
    },
    "英文": {
        "女声": [
            {"name": "Jenny (美国女声)", "id": "en-US-JennyNeural", "style": "友好", "description": "友好、自然的美式英语女声"},
            {"name": "Sonia (英国女声)", "id": "en-GB-SoniaNeural", "style": "优雅", "description": "优雅、清晰的英式英语女声"},
            {"name": "Aria (美国女声)", "id": "en-US-AriaNeural", "style": "专业", "description": "专业、清晰的女声"},
            {"name": "Emma (英国女声)", "id": "en-GB-EmmaNeural", "style": "柔和", "description": "柔和、细腻的英式女声"},
        ],
        "男声": [
            {"name": "Guy (美国男声)", "id": "en-US-GuyNeural", "style": "稳重", "description": "稳重、可靠的美式英语男声"},
            {"name": "Ryan (英国男声)", "id": "en-GB-RyanNeural", "style": "专业", "description": "专业、清晰的英式英语男声"},
            {"name": "Davis (美国男声)", "id": "en-US-DavisNeural", "style": "磁性", "description": "富有磁性的男声"},
        ]
    },
    "日语": {
        "女声": [
            {"name": "七海 (温柔女声)", "id": "ja-JP-NanamiNeural", "style": "温柔", "description": "温柔、自然的日语女声"},
            {"name": "香织 (可爱女声)", "id": "ja-JP-KaoriNeural", "style": "可爱", "description": "可爱、活泼的日语女声"},
        ],
        "男声": [
            {"name": "圭太 (男声)", "id": "ja-JP-KeitaNeural", "style": "稳重", "description": "稳重、成熟的日语男声"},
        ]
    },
    "韩语": {
        "女声": [
            {"name": "Sun-Hi (女声)", "id": "ko-KR-SunHiNeural", "style": "温柔", "description": "温柔、自然的韩语女声"},
        ],
        "男声": [
            {"name": "InJoon (男声)", "id": "ko-KR-InJoonNeural", "style": "稳重", "description": "稳重、成熟的韩语男声"},
        ]
    },
    "法语": {
        "女声": [
            {"name": "Denise (女声)", "id": "fr-FR-DeniseNeural", "style": "优雅", "description": "优雅、清晰的法语女声"},
        ],
        "男声": [
            {"name": "Henri (男声)", "id": "fr-FR-HenriNeural", "style": "稳重", "description": "稳重、成熟的法语男声"},
        ]
    },
    "德语": {
        "女声": [
            {"name": "Katja (女声)", "id": "de-DE-KatjaNeural", "style": "专业", "description": "专业、清晰的德语女声"},
        ],
        "男声": [
            {"name": "Conrad (男声)", "id": "de-DE-ConradNeural", "style": "稳重", "description": "稳重、成熟的德语男声"},
        ]
    },
    "西班牙语": {
        "女声": [
            {"name": "Elvira (女声)", "id": "es-ES-ElviraNeural", "style": "热情", "description": "热情、活泼的西班牙语女声"},
            {"name": "Dalia (墨西哥女声)", "id": "es-MX-DaliaNeural", "style": "友好", "description": "友好、自然的墨西哥西班牙语女声"},
        ],
        "男声": [
            {"name": "Alvaro (男声)", "id": "es-ES-AlvaroNeural", "style": "稳重", "description": "稳重、成熟的西班牙语男声"},
        ]
    }
}

# 侧边栏设置
with st.sidebar:
    st.header("⚙️ 设置")
    
    # 选择TTS引擎
    engine = st.selectbox(
        "选择语音引擎",
        ["Edge TTS (微软，推荐)", "Google TTS (免费)", "本地TTS (pyttsx3)"],
        help="Edge TTS: 微软免费引擎，音质好 | Google TTS: 免费但有速率限制 | 本地TTS: 无需网络"
    )
    
    # 语言选择
    language = st.selectbox(
        "选择语言",
        ["中文", "英文", "日语", "韩语", "法语", "德语", "西班牙语"],
        index=0
    )
    
    # 音色选择（仅Edge TTS）
    if engine == "Edge TTS (微软，推荐)":
        st.markdown("---")
        st.subheader("🎭 音色选择")
        
        # 显示当前语言的可用音色
        if language in VOICE_DATABASE:
            voice_categories = VOICE_DATABASE[language]
            
            # 选择性别分类
            gender = st.radio("选择性别", list(voice_categories.keys()), horizontal=True)
            
            # 显示音色按钮
            voices = voice_categories[gender]
            
            # 创建音色按钮网格
            cols = st.columns(3)
            for i, voice in enumerate(voices):
                col_idx = i % 3
                with cols[col_idx]:
                    # 检查是否是当前选中的音色
                    is_selected = (st.session_state.selected_voice == voice["id"])
                    
                    # 创建按钮
                    if st.button(
                        f"🎤 {voice['name']}",
                        key=f"voice_{voice['id']}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True,
                        help=voice["description"]
                    ):
                        st.session_state.selected_voice = voice["id"]
                        st.rerun()
            
            # 随机音色按钮
            if st.button("🎲 随机音色", use_container_width=True):
                random_voice = random.choice(voices)
                st.session_state.selected_voice = random_voice["id"]
                st.rerun()
            
            # 显示当前选择的音色信息
            current_voice_info = next((v for v in voices if v["id"] == st.session_state.selected_voice), None)
            if current_voice_info:
                st.info(f"**当前音色**: {current_voice_info['name']} ({current_voice_info['style']})")
        
        # 音色预览文本
        preview_text = st.text_input("音色预览文本", 
                                     value="欢迎使用文字转语音播放器。这是一个测试音频。",
                                     max_chars=50,
                                     help="输入简短文本测试音色效果")
        
        if st.button("🔊 测试音色", use_container_width=True):
            with st.spinner("正在生成测试音频..."):
                try:
                    # 使用Edge TTS生成测试音频
                    async def test_voice():
                        communicate = edge_tts.Communicate(
                            text=preview_text,
                            voice=st.session_state.selected_voice,
                            rate="+0%",
                            volume="+0%"
                        )
                        
                        audio_data = b""
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                audio_data += chunk["data"]
                        
                        return audio_data
                    
                    test_audio = asyncio.run(test_voice())
                    
                    if test_audio:
                        # 播放测试音频
                        st.audio(test_audio, format="audio/mp3")
                        st.success("✅ 音色测试完成")
                    else:
                        st.error("测试音频生成失败")
                        
                except Exception as e:
                    st.error(f"音色测试失败: {str(e)}")
    
    # 音高和语速设置
    st.markdown("---")
    st.subheader("🎵 语音参数")
    
    col_speed, col_pitch = st.columns(2)
    with col_speed:
        speed = st.slider("语速", 0.5, 2.0, 1.0, 0.1, help="数值越大语速越快")
    
    with col_pitch:
        pitch = st.slider("音高", -20, 20, 0, 1, help="调整语音的音调高低")
    
    volume = st.slider("音量", 0.1, 1.0, 0.8, 0.1)
    
    # 音频格式选择
    audio_format = st.selectbox("音频格式", ["MP3", "WAV"], index=0)
    
    st.markdown("---")
    st.subheader("📝 示例文本")
    
    # 示例文本
    example_texts = {
        "中文": "欢迎使用文字转语音播放器！这是一个简单易用的工具，可以将任何文本转换为语音。",
        "英文": "Welcome to the Text to Speech Player! This is an easy-to-use tool that can convert any text to speech.",
        "日语": "テキスト音声変換プレイヤーへようこそ！これはどんなテキストも音声に変換できる使いやすいツールです。",
        "韩语": "텍스트 음성 변환 플레이어에 오신 것을 환영합니다! 어떤 텍스트든 음성으로 변환할 수 있는 사용하기 쉬운 도구입니다。",
        "法语": "Bienvenue dans le lecteur de synthèse vocale! C'est un outil facile à utiliser qui peut convertir n'importe quel texte en parole.",
        "德语": "Willkommen beim Text-zu-Sprache-Player! Dies ist ein einfach zu bedienendes Tool, das jeden Text in Sprache umwandeln kann.",
        "西班牙语": "¡Bienvenido al reproductor de texto a voz! Esta es una herramienta fácil de usar que puede convertir cualquier texto en voz."
    }
    
    if st.button("加载示例", use_container_width=True):
        st.session_state.input_text = example_texts.get(language, example_texts["中文"])
        st.rerun()

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

# 主界面布局
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 输入文本")
    
    # 文本输入区域
    text_input = st.text_area(
        "请输入要转换的文本",
        value=st.session_state.input_text,
        height=300,
        placeholder="在此输入要转换为语音的文本...",
        key="text_input_area",
        help="建议文本长度不超过2000字符，支持中英文混合"
    )
    
    # 文本统计
    char_count = len(text_input)
    st.caption(f"字符数: {char_count}")
    
    # 文本处理选项
    with st.expander("文本处理选项"):
        col_proc1, col_proc2 = st.columns(2)
        with col_proc1:
            remove_empty_lines = st.checkbox("删除空行", value=True)
            add_pauses = st.checkbox("添加停顿", value=True)
        
        with col_proc2:
            auto_punctuation = st.checkbox("自动标点", value=True)
    
    # 处理文本
    processed_text = text_input
    if remove_empty_lines:
        processed_text = "\n".join([line for line in processed_text.splitlines() if line.strip()])
    if add_pauses:
        processed_text = processed_text.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n")
        processed_text = processed_text.replace(".", ".\n").replace("!", "!\n").replace("?", "?\n")
    
    # 控制按钮
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns([1, 1, 1, 1])
    
    with col_btn1:
        if st.button("🚀 生成语音", type="primary", use_container_width=True, icon="🔊"):
            if not text_input.strip():
                st.warning("请输入文本内容")
            else:
                st.session_state.input_text = text_input
                st.session_state.audio_generated = False
                # 触发重新运行，以便显示进度
                st.rerun()
    
    with col_btn2:
        if st.button("🗑️ 清除", use_container_width=True, icon="🗑️"):
            st.session_state.input_text = ""
            st.session_state.audio_data = None
            st.session_state.audio_generated = False
            st.rerun()
    
    with col_btn3:
        if st.button("📋 复制文本", use_container_width=True, icon="📋"):
            st.write("文本已复制到剪贴板")
    
    with col_btn4:
        if st.session_state.audio_data:
            download_disabled = False
        else:
            download_disabled = True
        
        st.button("💾 下载", disabled=download_disabled, use_container_width=True, icon="💾")

with col2:
    st.subheader("🎵 音频播放器")
    
    # 显示音频播放器
    if st.session_state.audio_data and st.session_state.audio_generated:
        # 显示当前音色信息
        current_voice_name = "未知音色"
        if language in VOICE_DATABASE:
            for gender, voices in VOICE_DATABASE[language].items():
                for voice in voices:
                    if voice["id"] == st.session_state.selected_voice:
                        current_voice_name = voice["name"]
                        break
        
        st.markdown(f"**当前音色**: {current_voice_name}")
        
        # 主播放器
        st.audio(st.session_state.audio_data, format=f"audio/{st.session_state.audio_format}")
        
        # 备用播放器（使用HTML5）
        st.markdown("### 备用播放器")
        b64 = base64.b64encode(st.session_state.audio_data).decode()
        audio_html = f"""
        <audio controls autoplay style="width: 100%; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            您的浏览器不支持音频播放
        </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
        
        # 音频信息
        st.markdown("### 📊 音频信息")
        audio_size = len(st.session_state.audio_data) / 1024  # KB
        
        info_col1, info_col2, info_col3 = st.columns(3)
        with info_col1:
            st.metric("文件大小", f"{audio_size:.1f} KB")
        with info_col2:
            st.metric("音频格式", st.session_state.audio_format.upper())
        with info_col3:
            st.metric("生成时间", datetime.now().strftime("%H:%M"))
        
        # 下载链接
        st.markdown("---")
        st.markdown("### 💾 下载选项")
        
        if st.session_state.audio_format == "mp3":
            mime_type = "audio/mpeg"
            file_ext = "mp3"
        else:
            mime_type = "audio/wav"
            file_ext = "wav"
            
        b64 = base64.b64encode(st.session_state.audio_data).decode()
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            href1 = f'<a href="data:{mime_type};base64,{b64}" download="speech.{file_ext}" style="display: block; padding: 10px; background-color: #4CAF50; color: white; text-align: center; border-radius: 5px; text-decoration: none;">下载音频文件</a>'
            st.markdown(href1, unsafe_allow_html=True)
        
        with col_dl2:
            href2 = f'<a href="data:{mime_type};base64,{b64}" download="{current_voice_name}.{file_ext}" style="display: block; padding: 10px; background-color: #2196F3; color: white; text-align: center; border-radius: 5px; text-decoration: none;">下载为：{current_voice_name[:10]}...</a>'
            st.markdown(href2, unsafe_allow_html=True)
        
        # 分享选项
        st.markdown("### 📤 分享")
        share_text = f"我用文字转语音播放器生成了语音，使用音色：{current_voice_name}"
        st.code(share_text, language="text")
        
    else:
        # 显示等待界面
        st.info("👆 输入文本并点击'生成语音'按钮")
        
        # 创建更美观的等待界面
        st.markdown("""
        <div style='text-align: center; padding: 60px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white;'>
            <h1 style='font-size: 80px; margin: 0;'>🔊</h1>
            <h3 style='margin: 20px 0 10px 0;'>等待生成音频</h3>
            <p style='color: rgba(255,255,255,0.8);'>选择音色，输入文本，点击生成按钮</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 显示当前选择的音色预览
        if engine == "Edge TTS (微软，推荐)" and language in VOICE_DATABASE:
            current_voice_info = None
            for gender, voices in VOICE_DATABASE[language].items():
                for voice in voices:
                    if voice["id"] == st.session_state.selected_voice:
                        current_voice_info = voice
                        break
            
            if current_voice_info:
                st.markdown(f"""
                <div style='background-color: #f0f8ff; padding: 15px; border-radius: 10px; margin-top: 20px; border-left: 5px solid #2196F3;'>
                    <h4 style='margin: 0 0 10px 0; color: #333;'>🎭 当前选择的音色</h4>
                    <p style='margin: 5px 0;'><strong>名称:</strong> {current_voice_info['name']}</p>
                    <p style='margin: 5px 0;'><strong>风格:</strong> {current_voice_info['style']}</p>
                    <p style='margin: 5px 0; color: #666;'>{current_voice_info['description']}</p>
                </div>
                """, unsafe_allow_html=True)

# 转换函数 - Google TTS
def convert_with_gtts(text, lang_code, speed=1.0):
    """使用Google TTS转换文本为语音"""
    try:
        # 调整语速
        slow = speed < 1.0
        
        # 使用gTTS生成语音
        tts = gTTS(text=text, lang=lang_code, slow=slow)
        
        # 保存到内存
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        # 返回字节数据
        return audio_bytes.read()
    except Exception as e:
        st.error(f"Google TTS转换失败: {str(e)}")
        return None

# 转换函数 - Edge TTS
async def convert_with_edge_tts_async(text, voice, rate, volume):
    """异步使用Edge TTS转换文本为语音"""
    try:
        # 创建Communicate对象
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=f"{rate:+d}%",
            volume=f"{volume:+d}%"
        )
        
        # 收集音频数据
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        return audio_data
    except Exception as e:
        st.error(f"Edge TTS转换失败: {str(e)}")
        return None

def convert_with_edge_tts(text, voice, rate, volume):
    """包装Edge TTS异步函数"""
    return asyncio.run(convert_with_edge_tts_async(text, voice, rate, volume))

# 转换函数 - 本地TTS (pyttsx3)
def convert_with_local_tts(text, lang, speed=1.0):
    """使用本地TTS引擎转换文本为语音"""
    try:
        import pyttsx3
        
        # 初始化引擎
        engine = pyttsx3.init()
        
        # 设置属性
        engine.setProperty('rate', int(150 * speed))
        engine.setProperty('volume', volume)
        
        # 尝试设置语言
        if lang == "zh-CN":
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_path = tmp_file.name
        
        # 保存到文件
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        
        # 读取文件
        with open(tmp_path, 'rb') as f:
            audio_data = f.read()
        
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        return audio_data
    except ImportError:
        st.warning("pyttsx3未安装，使用pip install pyttsx3安装")
        return None
    except Exception as e:
        st.error(f"本地TTS转换失败: {str(e)}")
        return None

# 主要转换逻辑
if st.session_state.input_text and not st.session_state.audio_generated:
    with st.spinner("正在生成语音，请稍候..."):
        try:
            # 使用处理后的文本
            text_to_convert = processed_text if 'processed_text' in locals() else st.session_state.input_text
            
            # 根据选择的引擎进行转换
            if engine == "Edge TTS (微软，推荐)":
                # 计算参数
                rate_adjust = int((speed - 1.0) * 100)
                volume_adjust = int((volume - 0.5) * 100)
                
                # 使用选择的音色
                voice_id = st.session_state.selected_voice
                
                audio_data = convert_with_edge_tts(
                    text_to_convert, 
                    voice_id, 
                    rate_adjust, 
                    volume_adjust
                )
                st.session_state.audio_format = "mp3"
                
            elif engine == "Google TTS (免费)":
                lang_code = language_codes[language]
                audio_data = convert_with_gtts(text_to_convert, lang_code, speed)
                st.session_state.audio_format = "mp3"
                
            else:  # 本地TTS
                lang_code = language_codes[language]
                audio_data = convert_with_local_tts(text_to_convert, lang_code, speed)
                st.session_state.audio_format = "wav"
            
            if audio_data:
                st.session_state.audio_data = audio_data
                st.session_state.audio_generated = True
                
                # 显示成功消息
                success_msg = st.success("✅ 语音生成成功！")
                time.sleep(0.5)  # 短暂延迟
                st.rerun()
            else:
                st.error("语音生成失败，请重试或更换引擎")
                
        except Exception as e:
            st.error(f"转换过程中发生错误: {str(e)}")

# 添加音色展示
with st.expander("🎭 音色库展示"):
    st.markdown("### 可用音色预览")
    
    selected_language = st.selectbox("选择语言查看音色", list(VOICE_DATABASE.keys()), key="voice_preview_lang")
    
    if selected_language in VOICE_DATABASE:
        voice_categories = VOICE_DATABASE[selected_language]
        
        for gender, voices in voice_categories.items():
            st.markdown(f"#### {gender}")
            
            for voice in voices:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"""
                    **{voice['name']}**  
                    *风格*: {voice['style']}  
                    {voice['description']}
                    """)
                
                with col2:
                    if st.button(f"选择{voice['name'].split()[0]}", 
                                 key=f"select_{voice['id']}",
                                 use_container_width=True):
                        st.session_state.selected_voice = voice["id"]
                        st.session_state.input_text = example_texts.get(selected_language, example_texts["中文"])
                        st.rerun()

# 添加使用说明
with st.expander("📖 使用说明"):
    st.markdown("""
    ### 🎯 使用方法：
    
    1. **输入文本**：在左侧文本框中输入或粘贴要转换的文本
    2. **选择音色**：在侧边栏中选择喜欢的语音音色（Edge TTS）
    3. **调整参数**：设置语速、音高、音量等参数
    4. **生成语音**：点击"生成语音"按钮
    5. **播放/下载**：在右侧播放音频或下载音频文件
    
    ### 🎭 音色特色：
    
    - **晓晓**：年轻自然，适合大部分场景
    - **晓伊**：温柔细腻，适合讲述故事
    - **云希**：成熟稳重，适合正式场合
    - **Jenny**：友好自然的美式英语
    - **Sonia**：优雅清晰的英式英语
    
    ### 💡 小技巧：
    
    - 点击"随机音色"按钮发现惊喜
    - 使用"测试音色"功能快速预览
    - 调整语速和音高创造个性化语音
    - 利用文本处理选项优化朗读效果
    """)

# 添加故障排除
with st.expander("🔧 常见问题"):
    st.markdown("""
    ### ❓ 音频无法播放？
    
    1. **使用备用播放器**：主播放器有问题时，备用播放器通常可以工作
    2. **检查网络**：Edge TTS和Google TTS需要网络连接
    3. **更换浏览器**：建议使用Chrome或Edge浏览器
    4. **减少文本长度**：过长的文本可能导致转换失败
    
    ### 🎵 音色选择不生效？
    
    1. **确认引擎**：音色选择仅对Edge TTS有效
    2. **检查语言**：确保音色语言与文本语言匹配
    3. **刷新页面**：有时需要刷新页面更新设置
    
    ### 📱 最佳体验：
    
    - **Edge TTS**：推荐使用，音质好，选择多
    - **中短文本**：建议不超过1000字符
    - **分段处理**：长文本可以分段转换
    - **保存设置**：找到喜欢的音色后，可以记住设置
    """)

# 页脚
st.markdown("---")
footer_col1, footer_col2 = st.columns([2, 1])
with footer_col1:
    st.markdown("""
    **🔊 文字转语音播放器** | 支持多音色多语言 | 免费使用  
    *使用Edge TTS、Google TTS和本地TTS引擎*
    """)
with footer_col2:
    st.markdown("""
    <div style='text-align: right; color: #666;'>
        版本 2.0 | 支持音色切换
    </div>
    """, unsafe_allow_html=True)
