import json
import time
import argparse
from langchain_ollama import OllamaLLM

def home_work():
    print("This is Homework 1-Shashank Ranjan")

#**********
#Settting up Ollamna LLM of qwen3:8b
#*************
def getmy_OllamaLLM(mod_name="qwen3:8b",mod_temp=0.7):
    return OllamaLLM(model=mod_name,temperature=mod_temp)

def run_and_interact_llm(my_llm):

    print("Success, LLM Chat Started. Type 'EXIT' or 'END' to stop]n")

    while True:
        user_input = input("Your Input: ")
        if user_input.strip().upper() in ['EXIT', 'END']:
            print("Thanks for chatting. Good Bye")
            break;

        # Send a prompt to the model
        # Force LangChain to always return a dict by passing the prompt using the "input" key:
        #llm_response = my_llm.invoke("What is the difference between Deep Learning and Maching Learning?")
             #[HumanMessage(content=user_input)]
        llm_response = my_llm.invoke(user_input)
        print("LLM Engine:", llm_response)

#Planner Agent
def get_and_run_planner(llm_model,prompt_title,prompt_content):
    prompt = f"""
        You are the Planner agent.
        Your job: read the title and content, then propose:
        - exactly 3 topical tags
        - a summary of at most 25 words
        
        Return strict JSON:
        {{
          "prompt_tags": ["tag1", "tag2", "tag3"],
          "prompt_summary": "..."
        }}
        
        Title: {prompt_title}
        Content: {prompt_content}
    """

    response = llm_model.invoke(prompt)
    return response

#Reviewer Agent
def run_reviewer(llm_model,planner_output):
    prompt = f"""
        You are the Reviwer agent.
        Your job: Review the planner output (in JSON) for correctness. Fix tags or summary, if needed
        - ensure 3 relevant tagas
        - summary must be less than 25 words
        
        Return strict JSON:
        {{
          "reviewer_tags": ["tag1", "tag2", "tag3"],
          "reviewer_summary": "..."
        }}
        
        Planner Output: {planner_output}
    """

    response = llm_model.invoke(prompt)
    return response

def validate_for_json(str_val):
    #convert these string output to dictionary..
    try:
        return json.loads(str_val)
    except Exception:
        print("Error Could Not parse the string for JSON",str_val)
        raise

def finalize_and_summarize_output(pln_output,rev_output):
    
    pln_output_dict = validate_for_json(pln_output)
    rev_output_dict = validate_for_json(rev_output)
    
    final_output = {
    "tags": rev_output_dict.get("reviewer_tags", []),
    "summary": rev_output_dict.get("reviewer_summary", ""),
    "transcripts": {
        "planner_response": pln_output,
        "reviewer_response": rev_output
    }
}

    return final_output

def print_latencies():
    import numpy as np
    results = [36,93]
    p50 = np.percentile(results, 50)
    p95 = np.percentile(results, 95)
    p99 = np.percentile(results, 99)

    print(f"P50 (Median): {p50}")
    print(f"P95: {p95}")
    print(f"P99: {p99}")
    
#********
# Main Program--
#********


def cmnd_line_main_exec_orig():
    #initilize argument parser
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--input",required=True,help="file or path name for JSON data")
    my_parser.add_argument("--llm_model",default="qwen3:8b")
    my_parser.add_argument("--temperature",type=float,default=0.7)
    all_args = my_parser.parse_args()

    #read the file
    with open(all_args,"r") as f:
        json_data = validate_for_json(f.read())

    title = json_data["title"]
    content = json_data["content"]

    my_llm = getmy_OllamaLLM(mod_name=all_args.llm_model,mod_temp = all_args.temperature)
    #run_and_interact_llm(my_llm)

    #use planner ..
    print("working with Agent to get response from LLM.. pleas wait..\n")
    planner_start_time = time.time()
    #planner_response= get_and_run_planner(my_llm,"Test","How Machine Learning Differs from Deep Learning?")
    planner_response= get_and_run_planner(my_llm,title,content)
    planner_latency = time.time() - planner_start_time
    print(planner_response)
    
    
    print("working with Reviewer Agent to get response.. pleas wait..\n")
    reviewer_start_time = time.time()
    reviewer_response = run_reviewer(my_llm,planner_response)
    reviewer_latency = time.time() - reviewer_start_time
    print(reviewer_response)
    summary_out = finalize_and_summarize_output(planner_response,reviewer_response)
    print(summary_out)

    print("Latency in Seconds for both Planner and Reviewer\n")
    print(f"Planner Latency : {planner_latency} , Reviewer Latency : {reviewer_latency}")


def main_test(my_prompt):
    
    print(f"The prompt is: {my_prompt}")
    # Initialize the model
    #llm = getmy_OllamaLLM() 
    # I used a lighter version of LLM
    my_llm = getmy_OllamaLLM(mod_name="qwen3:4b")
    #run_and_interact_llm(my_llm)

    #use planner ..
    print("working with Agent to get response from LLM.. pleas wait..\n")
    planner_start_time = time.time()
    planner_response= get_and_run_planner(my_llm,"Test",my_prompt)
    planner_latency = time.time() - planner_start_time
    print(planner_response)
    
    
    print("working with Reviewer Agent to get response.. pleas wait..\n")
    reviewer_start_time = time.time()
    reviewer_response = run_reviewer(my_llm,planner_response)
    reviewer_latency = time.time() - reviewer_start_time
    print(reviewer_response)
    summary_out = finalize_and_summarize_output(planner_response,reviewer_response)
    print(summary_out)

    print("Latency Seconds for both Planner and Reviewer\n")
    print(f"Planner Latency : {planner_latency} , Reviewer Latency : {reviewer_latency}")


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--input", required=True, help="file path for JSON data")
    #my_parser.add_argument("--llm_model", default="qwen3:8b")
    my_parser.add_argument("--llm_model", default="qwen3:4b")
    my_parser.add_argument("--temperature", type=float, default=0.7)
    all_args = my_parser.parse_args()

    # Load JSON correctly
    with open(all_args.input, "r") as f:
        json_data = validate_for_json(f.read())

    title = json_data["title"]
    content = json_data["content"]

    my_llm = getmy_OllamaLLM(mod_name=all_args.llm_model,
                             mod_temp=all_args.temperature)

    print("Working with Planner Agent...\n")
    planner_start_time = time.time()
    planner_response = get_and_run_planner(my_llm, title, content)
    planner_latency = time.time() - planner_start_time
    print(planner_response)

    print("\nWorking with Reviewer Agent...\n")
    reviewer_start_time = time.time()
    reviewer_response = run_reviewer(my_llm, planner_response)
    reviewer_latency = time.time() - reviewer_start_time
    print(reviewer_response)

    summary_out = finalize_and_summarize_output(planner_response, reviewer_response)
    print("\n=== FINAL OUTPUT ===")
    print(json.dumps(summary_out, indent=2))

    print("\nLatency (Seconds):")
    print(f"Planner: {planner_latency}")
    print(f"Reviewer: {reviewer_latency}")


home_work()
print("Building of two tiny agents that talk to each other")

#user_prompt = "What is the difference between Machine Learning and Deep Learning"
#main_test(user_prompt)

if __name__ == "__main__":
    main()

#C:\ASR Work\LearnPython\PythonApplication1\PythonApplication1
#python agents_demo.py --input nondeterminism_input.json
#python agents_demo.py --input nondeterminism_input.json --temperature 0.0 > reports/hw01/raw/run_00_test.txt
