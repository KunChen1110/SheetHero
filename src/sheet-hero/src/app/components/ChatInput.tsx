import { useState } from "react";

interface ChatInputProperties {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSendMessage, disabled }: ChatInputProperties) {
  const [input, setInput] = useState("");
  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSendMessage(input.trim());
      setInput("");
    }
  }

  return (
    <div className="bg-transparent p-6 relative z-10">
      <form className="max-w-4xl mx-auto" onSubmit={handleSubmit}>
        <div
          className={`relative flex items-center bg-gray-800 rounded-2xl border transition-all shadow-lg
            ${disabled ? "border-gray-700/50 opacity-60" : "border-gray-700"}
		`}
        >
          <textarea
            className="flex-1 resize-none bg-transparent px-4 py-3 pr-12 text-sm text-gray-100 placeholder-gray-500"
            value={input}
            disabled={disabled}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
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
            className="absolute right-2 p-2 rounded-lg"
            type="submit"
            disabled={!input.trim() || disabled}
          >
            Send {/* TODO his should probably be an icon <--- */}
          </button>
        </div>
      </form>
    </div>
  );
}
