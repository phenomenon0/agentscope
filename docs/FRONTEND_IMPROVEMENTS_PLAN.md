# Frontend Improvements Plan

## 1. Issues Identified

### Current State
- ❌ No shadcn/ui installed
- ❌ No tool use/reasoning visibility (users can't see what the agent is doing)
- ⚠️ Basic styling - functional but not polished
- ⚠️ Missing step-by-step execution display like Claude/ChatGPT apps

### What Users See Now
1. Plan preview (streaming from Claude Haiku) - italic text
2. Final response
3. **MISSING**: Tool calls, reasoning steps, progress indicators

---

## 2. Proposed Solution

### Phase 1: Install shadcn/ui
```bash
cd frontend
npx shadcn@latest init
npx shadcn@latest add card badge separator scroll-area collapsible
```

### Phase 2: Add Tool Use Visibility

#### Backend Changes (Expose Tool Metadata)
Update `agentspace/api/app.py` to include tool call history in response:

```python
{
  "session_id": "...",
  "reply": "...",
  "metadata": {...},
  "attachments": [...],
  "tool_calls": [  # NEW
    {
      "tool_name": "search_players_tool",
      "status": "running" | "completed" | "failed",
      "input": {"player_name": "Bukayo Saka"},
      "output": "Found player...",
      "timestamp": "2025-10-30T...",
      "duration_ms": 450
    }
  ]
}
```

#### Frontend Changes (Display Tool Steps)
Create new component: `ToolExecutionTimeline.tsx`

**Visual Design (like Claude/ChatGPT):**
```
┌─────────────────────────────────────┐
│ 🤔 Thinking...                      │
├─────────────────────────────────────┤
│ 🔍 search_players_tool              │
│ ├─ Input: {player_name: "Saka"}    │
│ └─ ✓ Found player (450ms)          │
│                                     │
│ 📊 player_season_summary_tool       │
│ ├─ Input: {player_id: 123...}      │
│ └─ ✓ Retrieved stats (1.2s)        │
│                                     │
│ 📈 plot_pizza_chart_tool            │
│ ├─ Generating radar chart...       │
│ └─ ✓ Chart created (2.3s)          │
└─────────────────────────────────────┘
```

### Phase 3: Polish Components with shadcn

#### Update Components
- `MessageBubble.tsx` → Use shadcn `Card`
- `Sidebar.tsx` → Use shadcn `Badge`, `Separator`
- `ChatPanel.tsx` → Use shadcn `ScrollArea`
- Add new `ToolExecutionTimeline.tsx` component

#### Visual Improvements
- Better shadows and depth
- Smooth animations
- Loading skeletons
- Better color hierarchy
- Icon system (lucide-react already installed)

---

## 3. Implementation Steps

### Step 1: Set up shadcn/ui
```bash
cd frontend
npx shadcn@latest init
# Choose:
# - Style: Default
# - Base color: Neutral
# - CSS variables: Yes
```

### Step 2: Install shadcn components
```bash
npx shadcn@latest add card
npx shadcn@latest add badge
npx shadcn@latest add separator
npx shadcn@latest add scroll-area
npx shadcn@latest add collapsible
npx shadcn@latest add skeleton
```

### Step 3: Update Backend API
Modify `agentspace/api/app.py`:
- Extract tool call history from agent memory
- Add to response payload
- Include timing information

### Step 4: Create ToolExecutionTimeline Component
```typescript
type ToolCall = {
  id: string;
  tool_name: string;
  status: "running" | "completed" | "failed";
  input: Record<string, unknown>;
  output?: string;
  timestamp: string;
  duration_ms?: number;
};

export function ToolExecutionTimeline({ toolCalls }: { toolCalls: ToolCall[] }) {
  // Render collapsible timeline with icons and status
}
```

### Step 5: Update ChatPanel to Display Tool Steps
- Add `toolCalls` to message state
- Render `ToolExecutionTimeline` before final response
- Show loading states for in-progress tools

### Step 6: Polish All Components
- Replace div cards with shadcn `Card`
- Use `Badge` for status indicators
- Add smooth transitions
- Better loading states

---

## 4. Expected Result

### Before
```
User: How is Bukayo Saka performing?

[Plan preview: checking player stats...]

Agent: Bukayo Saka has scored 14 goals...
```

### After
```
User: How is Bukayo Saka performing?

[Plan preview: checking player stats...]

┌─ Tool Execution ──────────────────┐
│ ✓ search_players_tool (450ms)    │
│ ✓ player_season_summary (1.2s)   │
│ ⏳ plot_pizza_chart (running...)  │
└───────────────────────────────────┘

Agent: Bukayo Saka has scored 14 goals...
[Pizza chart visualization]
```

---

## 5. Wireframe: Tool Execution Display

```
┌─────────────────────────────────────────────────┐
│ User Message                                    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Assistant (Thinking)                            │
├─────────────────────────────────────────────────┤
│ Tool Execution Steps:                           │
│                                                 │
│ [✓] search_players_tool               450ms    │
│     └─ Found: Bukayo Saka (#1234)              │
│                                                 │
│ [✓] player_season_summary_tool        1.2s     │
│     └─ Retrieved 2024/25 season stats          │
│                                                 │
│ [⏳] plot_pizza_chart_tool            running   │
│     └─ Generating radar chart...               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Assistant Response                              │
│                                                 │
│ Bukayo Saka has been excellent this season...  │
│                                                 │
│ [Visualization: Pizza Chart]                    │
└─────────────────────────────────────────────────┘
```

---

## 6. Files to Create/Modify

### New Files
- `frontend/components/ui/*.tsx` (shadcn components)
- `frontend/components/ToolExecutionTimeline.tsx`
- `frontend/lib/utils.ts` (for cn() helper)

### Modified Files
- `frontend/components/MessageBubble.tsx`
- `frontend/components/ChatPanel.tsx`
- `frontend/components/Sidebar.tsx`
- `frontend/lib/store/chat-store.ts` (add toolCalls to state)
- `agentspace/api/app.py` (expose tool call metadata)
- `frontend/tailwind.config.ts` (shadcn config)
- `frontend/app/globals.css` (shadcn styles)

---

## 7. Timeline

- **Phase 1** (shadcn setup): 15 min
- **Phase 2** (tool visibility backend): 30 min
- **Phase 3** (tool visibility frontend): 45 min
- **Phase 4** (polish components): 30 min

**Total: ~2 hours**
