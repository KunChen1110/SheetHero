import { useState } from "react";
import { Send } from "lucide-react";
import { ClarificationControl, ClarificationResponseSchema } from "@/util/interfaces";

// Properties needed for the app input
interface AppInputProperties {
  onSendMessage: (message: string, displayMessage?: string) => void;
  hasApiKey?: boolean;
  hasActiveChat?: boolean;
  isTyping?: boolean;
  outputMode: "file" | "text";
  onOutputModeChange: (mode: "file" | "text") => void;
  responseSchema?: ClarificationResponseSchema;
}

export function AppInput({
  onSendMessage,
  hasApiKey,
  hasActiveChat,
  isTyping,
  outputMode,
  onOutputModeChange,
  responseSchema,
}: AppInputProperties) {
  // The input text shown on the input container
  const [input, setInput] = useState("");
  const [controlValues, setControlValues] = useState<Record<string, string>>({});
  const [controlErrors, setControlErrors] = useState<Record<string, string>>({});

  // Passes arguments to a given "onSendMessage" function, then resets the input text
  function handleSubmit(event: React.FormEvent): void {
    event.preventDefault();

    if (input.trim() && !isTyping && hasApiKey && hasActiveChat) {
      onSendMessage(input.trim());
      setInput("");
    }
  }

  function handleControlValueChange(control: ClarificationControl, value: string): void {
    setControlValues((prev) => ({
      ...prev,
      [control.decision_kind]: value,
    }));
    setControlErrors((prev) => ({
      ...prev,
      [control.decision_kind]: "",
    }));
  }

  function validateControlInput(control: ClarificationControl, rawValue: string): string {
    const inputSpec = control.input;
    if (!inputSpec) return "";
    if (!rawValue.trim()) return "Please enter a value.";
    if (inputSpec.type !== "number") return "";

    const numericValue = Number(rawValue);
    if (!Number.isFinite(numericValue)) {
      return "Please enter a numeric value.";
    }
    if (inputSpec.min !== undefined && numericValue < inputSpec.min) {
      return inputSpec.validation_message || `Value must be at least ${inputSpec.min}.`;
    }
    if (inputSpec.max !== undefined && numericValue > inputSpec.max) {
      return inputSpec.validation_message || `Value must be at most ${inputSpec.max}.`;
    }
    return "";
  }

  function handleStructuredSubmit(control: ClarificationControl): void {
    if (isTyping || !hasApiKey || !hasActiveChat) return;

    const inputSpec = control.input;
    const payload: Record<string, unknown> = {
      decision_kind: control.decision_kind,
    };
    let displayMessage = control.label;

    if (inputSpec) {
      const rawValue = (controlValues[control.decision_kind] || "").trim();
      const validationError = validateControlInput(control, rawValue);
      if (validationError) {
        setControlErrors((prev) => ({
          ...prev,
          [control.decision_kind]: validationError,
        }));
        return;
      }
      payload[inputSpec.name || "value"] =
        inputSpec.type === "number" ? Number(rawValue) : rawValue;
      displayMessage = `${control.label}: ${rawValue}`;
    } else {
      payload.selected_option = control.label;
    }

    onSendMessage(JSON.stringify(payload), displayMessage);
    setControlValues({});
    setInput("");
  }

  function renderStructuredControls() {
    if (!responseSchema?.controls?.length) return null;
    const disabled = !hasApiKey || !hasActiveChat || isTyping;

    return (
      <div className="max-w-4xl mx-auto mb-3 rounded-2xl border border-(--sh-border-grey) bg-(--sh-darker-blue) p-3">
        <div className="mb-2 text-xs font-medium text-(--sh-grey)">
          Choose how SheetHero should handle this data issue:
        </div>
        <div className="flex flex-wrap gap-2">
          {responseSchema.controls.map((control) => {
            const inputSpec = control.input;
            const value = controlValues[control.decision_kind] || "";

            if (inputSpec) {
              return (
                <div
                  key={control.decision_kind}
                  className="flex flex-col gap-1 rounded-xl border border-(--sh-border-grey) bg-(--sh-dark-blue) p-2"
                >
                  <div className="flex items-center gap-2">
                    <input
                      className="w-40 rounded-lg border border-(--sh-border-grey) bg-(--sh-darker-blue) px-3 py-2 text-sm text-(--sh-white) placeholder-(--sh-grey) focus:outline-none disabled:opacity-50"
                      type={inputSpec.type === "number" ? "number" : "text"}
                      min={inputSpec.min}
                      max={inputSpec.max}
                      value={value}
                      disabled={disabled}
                      placeholder={inputSpec.placeholder || "Enter value"}
                      onChange={(event) => handleControlValueChange(control, event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          handleStructuredSubmit(control);
                        }
                      }}
                    />
                    <button
                      type="button"
                      disabled={disabled || !value.trim()}
                      onClick={() => handleStructuredSubmit(control)}
                      className="rounded-lg bg-(--sh-green) px-3 py-2 text-sm font-medium text-(--sh-white) hover:bg-(--sh-green-hover) disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {control.label}
                    </button>
                  </div>
                  {controlErrors[control.decision_kind] && (
                    <div className="px-1 text-xs text-red-300">
                      {controlErrors[control.decision_kind]}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <button
                key={control.decision_kind + control.label}
                type="button"
                disabled={disabled}
                onClick={() => handleStructuredSubmit(control)}
                className="rounded-xl border border-(--sh-border-grey) bg-(--sh-dark-blue) px-3 py-2 text-sm font-medium text-(--sh-white) hover:border-(--sh-green) disabled:cursor-not-allowed disabled:opacity-50"
              >
                {control.label}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // HTML for the app input
  return (
    <div className="p-6">
      {renderStructuredControls()}
      <form className="max-w-4xl mx-auto" onSubmit={handleSubmit}>
        <div className="flex items-center bg-(--sh-darker-blue) rounded-2xl border transition-all border-(--sh-border-grey)">
          {/* Text input area */}
          <textarea
            className="flex-1 resize-none p-4 text-sm text-(--sh-white) placeholder-(--sh-grey) focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            value={input}
            disabled={!hasApiKey || !hasActiveChat || isTyping}
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
                : !hasActiveChat
                  ? "Select a chat to start messaging..."
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
            disabled={!input.trim() || isTyping || !hasApiKey || !hasActiveChat}
          >
            <Send size={22} />
          </button>
        </div>
      </form>
    </div>
  );
}
