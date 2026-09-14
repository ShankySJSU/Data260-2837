# src/model_client.py

"""
Model Client Adapter for Homework 2
This file provides a unified interface for all LLM calls.
Required by TA – all agents MUST use this adapter.
"""

from langchain_ollama import OllamaLLM

def get_llm(model_name="qwen3:4b", temperature=0.7):
    """
    Returns an LLM adapter for Planner and Reviewer nodes.
    You may switch between qwen3:4b and qwen3:8b based on performance.
    """
    #this model is taking lots of time :Shasahnk
    model_name =  "qwen2.5:1.5b"
    #temperature = 0.0
    try:
        llm = OllamaLLM(model=model_name, temperature=temperature)
        return llm
    except Exception as e:
        raise RuntimeError(f"Failed to load model '{model_name}': {e}")

def call_llm(llm, prompt: str):
    """
    Unified method to send prompts to LLM.
    LangGraph nodes must call THIS function, not Ollama directly.
    """
    try:
        response = llm.invoke(prompt)
        return response
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}")