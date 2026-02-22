export function AppTypingIndicator() {
  //HTML for the typing indicator
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="text-lg text-(--sh-green-highlight)">Thinking</div>
      <div className="flex items-center gap-1">
        <div
          className="w-2 h-2 rounded-full bg-(--sh-green-highlight) animate-bounce"
          style={{ animationDelay: "0ms" }}
        ></div>
        <div
          className="w-2 h-2 rounded-full bg-(--sh-green-highlight) animate-bounce"
          style={{ animationDelay: "150ms" }}
        ></div>
        <div
          className="w-2 h-2 rounded-full bg-(--sh-green-highlight) animate-bounce"
          style={{ animationDelay: "300ms" }}
        ></div>
      </div>
    </div>
  );
}
