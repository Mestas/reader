"""
备用TTS引擎选项
"""
import pyttsx3
import edge_tts
import asyncio
import tempfile
import streamlit as st

class AlternativeTTS:
    """备用TTS引擎"""
    
    @staticmethod
    def get_engines():
        """获取可用的TTS引擎"""
        engines = []
        
        # 检查pyttsx3
        try:
            import pyttsx3
            engines.append("pyttsx3 (离线)")
        except:
            pass
        
        # 检查edge-tts
        try:
            import edge_tts
            engines.append("edge-tts (微软)")
        except:
            pass
        
        return engines
    
    @staticmethod
    def use_pyttsx3(text, lang='zh'):
        """使用pyttsx3（离线）"""
        try:
            import pyttsx3
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_path = tmp_file.name
            
            # 初始化引擎
            engine = pyttsx3.init()
            
            # 设置属性
            engine.setProperty('rate', 150)  # 语速
            engine.setProperty('volume', 0.9)  # 音量
            
            # 保存到文件
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            
            return temp_path
        except Exception as e:
            st.error(f"pyttsx3错误: {str(e)}")
            return None
    
    @staticmethod
    async def use_edge_tts_async(text, voice='zh-CN-XiaoxiaoNeural'):
        """使用edge-tts（异步）"""
        try:
            import edge_tts
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_path = tmp_file.name
            
            # 创建TTS对象
            communicate = edge_tts.Communicate(text, voice)
            
            # 保存音频
            await communicate.save(temp_path)
            return temp_path
        except Exception as e:
            st.error(f"edge-tts错误: {str(e)}")
            return None
    
    @staticmethod
    def use_edge_tts(text, voice='zh-CN-XiaoxiaoNeural'):
        """edge-tts的同步包装"""
        return asyncio.run(AlternativeTTS.use_edge_tts_async(text, voice))

# 在主应用中添加备用引擎选择
def add_tts_engine_selector():
    """添加TTS引擎选择器"""
    st.sidebar.subheader("🎙️ TTS引擎选择")
    
    engines = AlternativeTTS.get_engines()
    engines.insert(0, "gTTS (Google)")
    
    selected_engine = st.sidebar.selectbox(
        "选择TTS引擎",
        engines,
        help="gTTS可能有限制，可尝试其他引擎"
    )
    
    return selected_engine
