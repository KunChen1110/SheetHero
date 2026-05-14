import { useState, useRef, useEffect } from "react";
import { api } from "@/util/api";
import { useSettings } from "@/util/storage";
import { Chat, ClarificationResponseSchema, ExcelFile, Message, Role } from "@/util/interfaces";
import {
  loadAllChatsFromStorage,
  saveChatToStorage,
  deleteChatFromStorage,
} from "@/util/chatStorage";

import { MessageCircle } from "lucide-react";
import { Sidebar } from "@/renderer/app/components/Sidebar";
import { AppInput } from "@/renderer/app/components/AppInput";
import { AppMessage } from "@/renderer/app/components/AppMessage";
import { SettingsPopup } from "@/renderer/app/components/SettingsPopup";
import { AppAPIOverlay } from "@/renderer/app/components/AppAPIOverlay";
import { AppTypingIndicator } from "@/renderer/app/components/AppTypingIndicator";

export default function App() {
  // Save and load settings utility
  const { settings, saveSettings } = useSettings();

  // The array of chat histories
  const [chats, setChats] = useState<Chat[]>(() => loadAllChatsFromStorage());

  // The current active chat id
  const [activeChatId, setActiveChatId] = useState<string>();

  // The array of excel file interfaces active being used for query
  const [excelFiles, setExcelFiles] = useState<ExcelFile[]>([]);

  // If the model is considered to be typing
  const [isTyping, setIsTyping] = useState(false);

  // If the settings display is currently open
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Ref to keep track of whether we are waiting for a response from the backend
  const isWaitingRef = useRef(false);

  // Ref to keep track of the current session ID for ongoing conversations
  const sessionIdRef = useRef<string | null>(null);

  // Ref to cancel the active backend request from the UI.
  const activeRequestAbortRef = useRef<AbortController | null>(null);

  // Reference used to scroll to the bottom of the chat box
  const scrollReference = useRef<HTMLDivElement>(null);

  // The currently active chat
  const activeChat = chats.find((chat) => chat.id === activeChatId);

  // The active chat's messages, if it has any
  const messages = activeChat?.messages || [];

  // If there is an API key in use
  const hasApiKey = settings.apiKey.trim().length > 0;

  // The current output mode (file or text)
  const [outputMode, setOutputMode] = useState<"file" | "text">("file");

  // Delete a chat by id (must be inside App to access state)
  function handleDeleteChat(chatId: string) {
    setChats((prev) => {
      const updated = prev.filter((chat) => chat.id !== chatId);
      deleteChatFromStorage(chatId);
      // If the deleted chat was active, clear activeChatId
      if (activeChatId === chatId) setActiveChatId(undefined);
      return updated;
    });
  }

  // Update isWaiting state and keep the ref in sync immediately.
  function updateIsWaiting(value: boolean): void {
    isWaitingRef.current = value;
  }

  // Update sessionId state and keep the ref in sync immediately.
  function updateSessionId(value: string | null): void {
    sessionIdRef.current = value;
  }

  // Handles when the settings button is clicked
  function handleSettingsClick(): void {
    setIsSettingsOpen(true);
  }

  // Handles when a chat history was selected
  function handleChatSelect(chatId: string): void {
    setActiveChatId(chatId);
  }

  // Handles when the settings are saved
  function handleSaveSettings(
    apiKey: string,
    maxTurns: number,
    model: string,
    outputDir: string,
    baseURL?: string,
  ): void {
    saveSettings({
      apiKey: apiKey,
      maxTurns: maxTurns,
      model: model,
      outputDir: outputDir,
      baseURL: baseURL || "",
    });
  }

  // Scrolls to the bottom of the dialogue box
  function scrollToBottom(): void {
    scrollReference.current?.scrollIntoView({
      behavior: "smooth",
    });
  }

  // Automatically scrolls to the bottom of the dialogue box after typing or new message creation
  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Automatically load all chats from storage (in case localStorage changes externally)
  useEffect(() => {
    setChats(loadAllChatsFromStorage());
  }, []);

  // Creates a basic chat title for the chat history
  function generateChatTitle(firstMessage: string): string {
    const words = firstMessage.split(" ").slice(0, 4).join(" ");
    if (words.length > 30) return words.substring(0, 30) + "...";
    else return words;
  }

  // Creates a new chat with a default title and sets it as the active chat
  function createNewChat(): void {
    stopActiveRequest(false);
    const newChat: Chat = {
      id: Date.now().toString(),
      title: "New Chat",
      messages: [],
    };
    setChats((prev) => {
      const updated = [newChat, ...prev];
      saveChatToStorage(newChat);
      return updated;
    });
    setActiveChatId(newChat.id);
    updateSessionId(null);
    updateIsWaiting(false);
  }

  function appendAssistantMessage(content: string): void {
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: Role.ASSISTANT,
      content,
    };

    setChats((prevChats) => {
      const updated = prevChats.map((chat) =>
        chat.id === activeChatId
          ? { ...chat, messages: [...chat.messages, assistantMessage] }
          : chat,
      );
      const updatedChat = updated.find((chat) => chat.id === activeChatId);
      if (updatedChat) saveChatToStorage(updatedChat);
      return updated;
    });
  }

  function stopActiveRequest(addMessage = true): void {
    activeRequestAbortRef.current?.abort();
    activeRequestAbortRef.current = null;
    setIsTyping(false);
    updateIsWaiting(false);

    const activeSessionId = sessionIdRef.current;
    if (activeSessionId) {
      api.delete(`/sheet-hero/session/${activeSessionId}`).catch(console.error);
      updateSessionId(null);
    }

    if (addMessage) {
      appendAssistantMessage("Stopped.");
    }
  }

  // Creates a new message in the active chat and gets a response from the backend
  async function createNewMessage(content: string, displayContent?: string): Promise<void> {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: Role.USER,
      content: displayContent ?? content,
    };

    setChats((prevChats) => {
      const updated = prevChats.map((chat) =>
        chat.id === activeChatId
          ? {
              ...chat,
              messages: [...chat.messages, userMessage],
              title:
                chat.messages.length === 0
                  ? generateChatTitle(displayContent ?? content)
                  : chat.title,
            }
          : chat,
      );
      // Save updated chat
      const updatedChat = updated.find((c) => c.id === activeChatId);
      if (updatedChat) saveChatToStorage(updatedChat);
      return updated;
    });

    setIsTyping(true);
    const requestAbortController = new AbortController();
    activeRequestAbortRef.current = requestAbortController;

    try {
      let assistantContent: string;
      const waitingNow = isWaitingRef.current;
      const sessionNow = sessionIdRef.current;
      console.debug(
        `[SheetHero] send — isWaiting=${waitingNow}, sessionId=${sessionNow}`,
        "→ routing to:",
        waitingNow && sessionNow ? "sendReply" : "startConversation",
      );

      if (waitingNow && sessionNow) {
        assistantContent = await sendReply(content, requestAbortController.signal);
      } else {
        assistantContent = await startConversation(
          content,
          requestAbortController.signal,
        );
      }

      let parsedContent = assistantContent;
      let hasOutputFile = false;
      let outputPath: string | null = null;
      let detailsMarkdown = "";
      let uiThoughts = undefined;
      let responseSchema: ClarificationResponseSchema | undefined = undefined;

      try {
        const parsed = JSON.parse(assistantContent);
        parsedContent = parsed.message;
        hasOutputFile = parsed.has_output_file ?? false;
        outputPath = parsed.output_path ?? null;
        detailsMarkdown = parsed.details_markdown ?? "";
        uiThoughts = parsed.ui_thoughts ?? undefined;
        responseSchema = parsed.response_schema ?? undefined;
      } catch {
        // Not JSON, plain string response — that's fine
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: Role.ASSISTANT,
        content: parsedContent,
        hasOutputFile,
        outputPath,
        detailsMarkdown,
        uiThoughts,
        responseSchema,
      };

      setChats((prevChats) => {
        const updated = prevChats.map((chat) =>
          chat.id === activeChatId
            ? { ...chat, messages: [...chat.messages, assistantMessage] }
            : chat,
        );
        // Save updated chat
        const updatedChat = updated.find((c) => c.id === activeChatId);
        if (updatedChat) saveChatToStorage(updatedChat);
        return updated;
      });
    } catch (error) {
      if ((error as { code?: string })?.code === "ERR_CANCELED") {
        return;
      }
      console.error(error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: Role.ASSISTANT,
        content: "Error: Could not get response from backend",
      };
      setChats((prevChats) => {
        const updated = prevChats.map((chat) =>
          chat.id === activeChatId
            ? { ...chat, messages: [...chat.messages, errorMessage] }
            : chat,
        );
        // Save updated chat
        const updatedChat = updated.find((c) => c.id === activeChatId);
        if (updatedChat) saveChatToStorage(updatedChat);
        return updated;
      });
    } finally {
      if (activeRequestAbortRef.current === requestAbortController) {
        activeRequestAbortRef.current = null;
      }
      setIsTyping(false);
    }
  }

  // Creates a new session conversation
  async function startConversation(
    userMessage: string,
    signal?: AbortSignal,
  ): Promise<string> {
    const newSessionId = Date.now().toString();
    // updateSessionId keeps the ref in sync immediately so processEvents
    // (called after the await) reads the correct session ID via the ref.
    updateSessionId(newSessionId);

    const result = await api.post("/sheet-hero/start", {
      session_id: newSessionId,
      api_key: settings.apiKey,
      model: settings.model,
      max_turns: settings.maxTurns,
      base_url: settings.baseURL || "",
      output_file: settings.outputDir,
      output_mode: outputMode,
      prompt: userMessage,
      excel_paths: excelFiles.map((f) => f.path),
    }, {
      signal,
    });

    return processEvents(result.data.events);
  }

  // Sends a reply to an existing session
  async function sendReply(
    userReply: string,
    signal?: AbortSignal,
  ): Promise<string> {
    const result = await api.post("/sheet-hero/reply", {
      session_id: sessionIdRef.current,
      user_reply: userReply,
    }, {
      signal,
    });

    return processEvents(result.data.events);
  }

  // Handles specific event types from backend
  function processEvents(events: Record<string, unknown>[]): string {
    const allThoughts: unknown[] = [];
    for (const event of events) {
      if (Array.isArray(event.ui_thoughts)) {
        allThoughts.push(...event.ui_thoughts);
      }
    }

    for (const event of events) {
      const type = event.type;

      if (type === "clarification") {
        console.debug("[SheetHero] event=clarification → isWaiting=true");
        updateIsWaiting(true);
        return JSON.stringify({
          message: event.message,
          details_markdown: event.details_markdown || "",
          response_schema: event.response_schema || null,
          ui_thoughts: allThoughts,
        });
      }

      if (type === "final" || type === "error") {
        // Use the ref for sessionId — state may be stale inside this closure
        // (e.g. when called from startConversation after setSessionId was
        // called but before React committed the batch).
        const activeSessionId = sessionIdRef.current;
        console.debug(
          `[SheetHero] event=${type} → isWaiting=false, deleting session=${activeSessionId}`,
        );
        updateIsWaiting(false);
        if (activeSessionId) {
          api
            .delete(`/sheet-hero/session/${activeSessionId}`)
            .catch(console.error);
          updateSessionId(null);
        }
        return JSON.stringify({
          message: event.message,
          has_output_file: event.has_output_file ?? false,
          output_path: event.output_path ?? null,
          ui_thoughts: allThoughts,
        });
      }
    }

    return "Processing...";
  }

  // Renders the chat if there are existing chats with messages
  function renderChat() {
    return (
      <div className="max-w-3xl mx-auto space-y-4 py-5">
        {messages.map((message) => (
          <AppMessage
            key={message.id}
            role={message.role}
            content={message.content}
            hasOutputFile={message.hasOutputFile}
            outputPath={message.outputPath}
            detailsMarkdown={message.detailsMarkdown}
            uiThoughts={message.uiThoughts}
          />
        ))}
        <div ref={scrollReference} />
      </div>
    );
  }

  const activeResponseSchema = [...messages]
    .reverse()
    .find((message) => message.role === Role.ASSISTANT && message.responseSchema)
    ?.responseSchema;

  // Renders instructions to begin the conversation if there is an active chat but no messages
  function renderChatEmptyMessages() {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center text-center px-6">
        {/* Icon */}
        <div className="bg-(--sh-green) text-(--sh-white) rounded-full p-4 mb-4">
          <MessageCircle size={36} />
        </div>

        {/* Header */}
        <h2 className="text-2xl font-bold text-(--sh-white) mb-2">
          Start the Conversation
        </h2>

        {/* Instructions */}
        <p className="text-(--sh-grey) mb-6 max-w-xs">
          Type a message below to begin chatting with SheetHero about your Excel
          files.
        </p>
      </div>
    );
  }

  // Renders instructions to create a chat if there are no existing chats
  function renderEmptyChat() {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center text-center px-6">
        {/* Icon */}
        <div className="bg-(--sh-green) text-(--sh-white) rounded-full p-4 mb-4">
          <MessageCircle size={36} />
        </div>

        {/* Header */}
        <h2 className="text-2xl font-bold text-(--sh-white) mb-2">
          Create a New Conversation
        </h2>

        {/* Instructions */}
        <p className="text-(--sh-grey) mb-6 max-w-xs">
          You don’t have any chats yet. Click the New Chat button in the
          sidebar, or the button below to get started.
        </p>

        {/* Create new chat button */}
        <button
          onClick={createNewChat}
          className="px-6 py-3 bg-(--sh-green) text-(--sh-white) rounded-lg font-medium hover:bg-(--sh-green-hover) transition-colors"
        >
          + New Chat
        </button>
      </div>
    );
  }

  // HTML for the app
  return (
    <div className="h-full flex">
      {/* =-=-= Sidebar =-=-=*/}
      <Sidebar
        chats={chats}
        activeChat={activeChatId}
        files={excelFiles}
        onSettingsClick={handleSettingsClick}
        onFilesChange={setExcelFiles}
        onChatSelect={handleChatSelect}
        onNewChat={createNewChat}
        onDeleteChat={handleDeleteChat}
      />

      {/* =-=-= Main content =-=-= */}
      <div className="flex flex-1 flex-col p-5 pl-0">
        {/* =-=-=  Main container =-=-= */}
        <div className="h-full rounded-3xl border border-(--sh-border-grey) flex flex-col overflow-hidden bg-(--sh-dark-blue)">
          <div className="flex-1 overflow-y-auto p-6 relative">
            {/* Missing API key overlay */}
            {!hasApiKey && chats.length != 0 && (
              <div className="absolute top-0 left-0 right-0 p-2">
                <AppAPIOverlay onSettingsClick={handleSettingsClick} />
              </div>
            )}

            {/* Chats container */}
            {chats.length === 0 || !activeChatId
              ? renderEmptyChat()
              : messages.length === 0
                ? renderChatEmptyMessages()
                : renderChat()}

            {/* Typing indicator */}
            {isTyping && (
              <div className="flex justify-center">
                <AppTypingIndicator />
              </div>
            )}
          </div>
          <AppInput
            onSendMessage={createNewMessage}
            hasApiKey={hasApiKey}
            hasActiveChat={!!activeChatId}
            isTyping={isTyping}
            onStopThinking={stopActiveRequest}
            outputMode={outputMode}
            onOutputModeChange={setOutputMode}
            responseSchema={isWaitingRef.current ? activeResponseSchema : undefined}
          />
        </div>
      </div>
      {/* =-=-= Settings =-=-= */}
      <SettingsPopup
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSave={handleSaveSettings}
        apiKey={settings.apiKey}
        maxTurns={settings.maxTurns}
        model={settings.model}
        baseURL={settings.baseURL}
        outputDir={settings.outputDir}
      />
    </div>
  );
}
