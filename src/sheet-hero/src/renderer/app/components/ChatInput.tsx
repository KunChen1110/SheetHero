import { useState } from "react";
import { Send } from "lucide-react";

interface ChatInputProperties {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSendMessage, disabled }: ChatInputProperties) {
  // The input text shown on the input container
  const [input, setInput] = useState("");

  // Passes arguments to a given "onSendMessage" function, then resets the input text
  function handleSubmit(event: React.FormEvent): void {
    event.preventDefault();

    if (input.trim() && !disabled) {
      onSendMessage(input.trim());
      setInput("");
    }
  }

  // HTML for the chat input
  return (
    <div className="p-6">
      <form className="max-w-4xl mx-auto" onSubmit={handleSubmit}>
        <div
          className={`flex items-center bg-gray-800 rounded-2xl border transition-all ${
            disabled ? "border-gray-700/50 opacity-60" : "border-gray-700"
          }
        `}
        >
          {/* Text input area */}
          <textarea
            className="flex-1 resize-none p-4 text-sm text-gray-100 placeholder-gray-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            value={input}
            disabled={disabled}
            rows={1}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSubmit(event);
              }
            }}
            placeholder={
              disabled
                ? "Configure API key in settings to start..."
                : "Ask me a question"
            }
            style={{
              minHeight: "48px",
              maxHeight: "150px",
            }}
            onInput={(event) => {
              const target = event.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 200) + "px";
            }}
          />

          {/* Send input button */}
          <button
            className="mr-2 p-2 rounded-lg bg-green-500 text-white hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowe transition-all"
            type="submit"
            disabled={!input.trim() || disabled}
          >
            <Send size={22} />
          </button>
        </div>
      </form>
    </div>
  );
}
