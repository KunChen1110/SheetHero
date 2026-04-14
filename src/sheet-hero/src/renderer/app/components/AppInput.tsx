import { useState } from "react";
import { Send } from "lucide-react";

// Properties needed for the app input
interface AppInputProperties {
  onSendMessage: (message: string) => void;
  hasApiKey?: boolean;
  isTyping?: boolean;
    outputMode: "file" | "text";
  onOutputModeChange: (mode: "file" | "text") => void;
}

export function AppInput({
  onSendMessage,
  hasApiKey,
  isTyping,
  outputMode,
  onOutputModeChange,
}: AppInputProperties) {
  // The input text shown on the input container
  const [input, setInput] = useState("");

  // Passes arguments to a given "onSendMessage" function, then resets the input text
  function handleSubmit(event: React.FormEvent): void {
    event.preventDefault();

    if (input.trim() && !isTyping && hasApiKey) {
      onSendMessage(input.trim());
      setInput("");
    }
  }

  // HTML for the app input
  return (
    <div className="p-6">
      <form className="max-w-4xl mx-auto" onSubmit={handleSubmit}>
        <div className="flex items-center bg-(--sh-darker-blue) rounded-2xl border transition-all border-(--sh-border-grey)">
          {/* Text input area */}
          <textarea
            className="flex-1 resize-none p-4 text-sm text-(--sh-white) placeholder-(--sh-grey) focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            value={input}
            disabled={!hasApiKey || isTyping}
            rows={1}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSubmit(event);
              }
            }}
            placeholder={
              // Different hints depending on state
              !hasApiKey
                ? "Configure API key in settings to start..."
                : isTyping
                  ? "Thinking of a response..."
                  : "Ask me a question"
            }
            style={{
              minHeight: "50px",
              maxHeight: "150px",
            }}
            onInput={(event) => {
              const target = event.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 200) + "px";
            }}
          />

          {/* Output mode toggle */}
          <div className="mx-2 flex items-center bg-(--sh-dark-blue) border border-(--sh-border-grey) rounded-full p-0.5 text-xs font-medium shrink-0">
            <button
              type="button"
              onClick={() => onOutputModeChange("file")}
              className={`px-3 py-1 rounded-full transition-all ${
                outputMode === "file"
                  ? "bg-(--sh-green) text-(--sh-white)"
                  : "text-(--sh-grey) hover:text-(--sh-white)"
              }`}
            >
              File
            </button>
            <button
              type="button"
              onClick={() => onOutputModeChange("text")}
              className={`px-3 py-1 rounded-full transition-all ${
                outputMode === "text"
                  ? "bg-(--sh-green) text-(--sh-white)"
                  : "text-(--sh-grey) hover:text-(--sh-white)"
              }`}
            >
              Text
            </button>
          </div>

          {/* Send input button */}
          <button
            className="mr-2 p-2 rounded-lg bg-(--sh-green) text-(--sh-white) hover:bg-(--sh-green-hover) disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            type="submit"
            disabled={!input.trim() || isTyping || !hasApiKey}
          >
            <Send size={22} />
          </button>
        </div>
      </form>
    </div>
  );
}
