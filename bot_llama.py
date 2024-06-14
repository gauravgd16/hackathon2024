import os
from groq import Groq
import streamlit as st
st.set_page_config(
    page_title="SAP's Mental Health 24×7 Chatbot", 
    page_icon="💬")
groq_api_key=os.environ.get("GROQ_API_KEY")
st.title("SAP's AI-Driven Mental Health & Well Being Chatbot 🤖")
st.markdown(
    """
<style>
    .st-emotion-cache-janbn0 .st-emotion-cache-1c7y2kd {
        flex-direction: row-reverse;
        text-align: right;
    }
    .st-emotion-cache-jmw8un {
        width: 1.8rem;
        height: 1.5rem;
        background-color: rgb(9, 171, 59);
        
    }
    .st-emotion-cache-4zpzjl{
        width: 1.8rem;
        height: 1.5rem;
        background-color: rgb(252, 175, 69);
        
    }
</style>
""",
    unsafe_allow_html=True,
)
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Mental Health Chatbot is here to help you. How can I assist you today?"}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input():
    if not groq_api_key:
        st.info("Please add your Groq Cloud API key to continue.")
        st.stop()

    client = Groq(api_key=groq_api_key)
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    response = client.chat.completions.create(model="llama3-70b-8192", messages=st.session_state.messages)
    msg = response.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": msg})
    st.chat_message("assistant").write(msg)
