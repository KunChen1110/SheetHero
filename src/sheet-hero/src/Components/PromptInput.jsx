import { useState } from "react";

const PromptInput = ({ onSend }) => {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (!value.trim()) return;
    onSend?.(value);
    setValue("");
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      <div className="flex items-end gap-2 rounded-xl border border-gray bg-dark_gray p-3 shadow-sm focus-within:ring-2 focus-within:ring-gray-400">
        <textarea
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Send a message..."
          className="flex-1 resize-none bg-transparent text-sm outline-none"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />

        <button
          onClick={handleSend}
          disabled={!value.trim()}
          className="rounded-lg bg-light_green px-3 py-2 text-white disabled:opacity-40"
        >
          ➤
        </button>
        
      </div>
    </div>
  );
};

export default PromptInput;
