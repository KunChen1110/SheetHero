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
    <div className="p-6 relative">
      <form className="max-w-4xl mx-auto" onSubmit={handleSubmit}>
        <div
          className={`relative flex items-center bg-gray-800 rounded-2xl border transition-all ${
            disabled ? "border-gray-700/50 opacity-60" : "border-gray-700"
          }
        `}
        >
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
              maxHeight: "200px",
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 200) + "px";
            }}
          />

          <button
            className="absolute right-2 p-2 rounded-lg bg-linear-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:from-green-500 disabled:hover:to-green-600 transition-all"
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
