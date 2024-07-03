import os
import string
import random
import streamlit as st
from groq import Groq
from streamlit_chat import message

groq_api_key = os.environ.get("GROQ_API_KEY")

st.set_page_config(
    page_title="SAP's Mental Health 24×7 Chatbot", 
    page_icon="💬"
)
st.title(":blue[SAP's AI-Driven Mental Health & Well Being Chatbot 🤖]")

st.markdown(
    """
    <style>
        .st-emotion-cache-janbn0 {
            flex-direction: row-reverse;
            text-align: right;
        }
        .stChatMessage.st-emotion-cache-1c7y2kd.eeusbqq4[data-testid="stChatMessage"]{
            flex-direction: row-reverse;
            text-align: right;
        }
        .st-emotion-cache-jmw8un {
            background-color: rgb(0, 107, 184);
        }
        .st-emotion-cache-4zpzjl{
            background-color: rgb(255, 202, 75);
        }
        [data-testid="stToolbar"].st-emotion-cache-15ecox0.ezrtsby0 {
            display: none;
        }
        [data-testid="stChatMessageContent"] p{
        font-family: 'Arial', sans-serif;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

def get_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"key": get_key(), "role": "assistant", "content": "You are a compassionate and knowledgeable Mental Health and Wellbeing expert ChatBot of SAP company, dedicated to supporting employees at SAP. Your role involves providing accurate information and empathetic support concerning mental health and general wellbeing. Offer helpful advice, resources, and coping strategies with a focus on care and understanding. Share information about SAP's Mental Health & Wellbeing Program when relevant or upon request, ensuring the employee receives the best possible support tailored to their needs."}
    ]

message("SAP's Mental Health Chatbot is here to help you. How can I assist you today?", is_user=False, avatar_style="bottts", seed=123, key=get_key())

for msg in st.session_state.messages[1:]:
    message(msg["content"], is_user=msg["role"] == "user", avatar_style="avataaars" if msg["role"] == "user" else "bottts", seed=123, key=msg["key"])

if prompt := st.chat_input():
    if not groq_api_key:
        st.info("Please add your Groq Cloud API key to continue.")
        st.stop()
    
    user_key = get_key()
    st.session_state.messages.append({"key": user_key, "role": "user", "content": prompt})
    message(prompt, is_user=True, avatar_style="avataaars", seed=123, key=user_key)

    client = Groq(api_key=groq_api_key)
    response = client.chat.completions.create(model="llama3-70b-8192", messages=[{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.messages])
    msg_content = response.choices[0].message.content

    assistant_key = get_key()
    st.session_state.messages.append({"key": assistant_key, "role": "assistant", "content": msg_content})
    message(msg_content, is_user=False, avatar_style="bottts", seed=123, key=assistant_key)
