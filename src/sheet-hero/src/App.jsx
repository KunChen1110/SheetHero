import React from 'react';
import Sidebar from './Components/Sidebar';
import PromptInput from './Components/PromptInput';

function App() {
  return (
    <div className="flex h-screen p-2 gap-2">
      <Sidebar />

      <div className="flex flex-col flex-1 bg-dark_gray rounded-4xl p-2">
        
        <div className="flex-1 overflow-y-auto rounded-3xl bg-dark_gray"></div>

        <div className="border-t border-gray p-2">
          <PromptInput/>
        </div>

      </div>
    </div>
  );
}

export default App;