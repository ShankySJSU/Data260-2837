
import argparse
#from src.model_client import ModelClient
from model_client import ModelClient

#for execution .. I am running from same directory hence 

def main():
    parser = argparse.ArgumentParser()
    #parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

    client = ModelClient(model_name=args.model, temperature=args.temperature)

    conversation = []
    turn_count = 0
    cumulative_input = 0
    cumulative_output = 0

    # Initial system prompt
    system_prompt = "You are an assistant that responds concisely and politely."
    conversation.append({"role": "system", "content": system_prompt})

    while True:
        user_input = input("\nUser: ")

        if user_input.strip() == "/exit":
            print("\nExiting...")
            print(f"Total turns: {turn_count}")
            print(f"Cumulative input tokens: {cumulative_input}")
            print(f"Cumulative output tokens: {cumulative_output}")
            return

        if user_input.strip() == "/stats":
            hist_text = " ".join([m["content"] for m in conversation])
            hist_len = len(hist_text)
            print("\n--- /stats ---")
            print(f"Turn count: {turn_count}")
            print(f"Cumulative input tokens: {cumulative_input}")
            print(f"Cumulative output tokens: {cumulative_output}")
            print(f"Serialized conversation length (chars): {hist_len}")
            print("--- end /stats ---")
            continue

        conversation.append({"role": "user", "content": user_input})

        # Call model
        response, in_tok, out_tok, total_tok = client.complete(conversation)

        # Add assistant turn
        conversation.append({"role": "assistant", "content": response})

        turn_count += 1
        cumulative_input += in_tok
        cumulative_output += out_tok

        print("\nAssistant:", response)
        print(f"[Tokens] input={in_tok} output={out_tok} total={total_tok}")

if __name__ == "__main__":
    main()