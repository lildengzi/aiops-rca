import os
os.environ["DASHSCOPE_API_KEY"] = "sk-1adf74e6e36241119c97566f1f448e7e"  # 或已在环境变量中设置

from langchain_dashscope import ChatDashScope

llm = ChatDashScope(model="qwen-plus", temperature=0)
response = llm.invoke("你好，请简单介绍一下自己。")
print(response.content)