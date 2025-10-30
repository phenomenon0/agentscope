# Why the Visualization Fix Didn't Work

## What You Implemented ✅

You correctly implemented most of the solution from `VISUALIZATION_FIX_SOLUTION.md`:

### 1. Memory Extraction Function ✅
**Location:** `agentspace/api/app.py:158-271`

```python
async def _extract_tool_visualizations_from_memory(
    agent: ReActAgent,
    max_lookback: int = 12,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
```

This function:
- ✅ Reads agent memory
- ✅ Looks for visualization metadata (`viz_type`, `image_data`, `images`)
- ✅ Extracts base64 image data
- ✅ Extracts image paths
- ✅ Extracts ImageBlocks from content
- ✅ Returns attachments and metadata

### 2. Updated `agent_chat` Endpoint ✅
**Location:** `agentspace/api/app.py:580-626`

```python
async with lock:
    reply_msg = await agent.reply(...)
    tool_attachments, tool_metadata = await _extract_tool_visualizations_from_memory(agent)

# Merge attachments and metadata
attachments = _merge_attachment_lists(msg_attachments, tool_attachments)
final_metadata.update(tool_metadata)
```

This correctly:
- ✅ Calls extraction after agent.reply()
- ✅ Merges tool attachments with message attachments
- ✅ Merges tool metadata with reply metadata
- ✅ Returns merged data in ChatResponse

## Why It Didn't Work ❌

### **Critical Issue: Missing `/api/viz` Endpoint**

Your code generates URLs like `/api/viz?path=/plots/heatmap_12345.png` but **this endpoint doesn't exist**.

#### Evidence:

1. **Backend generates path URLs** (app.py:231, 248):
   ```python
   _add_src(f"/api/viz?path={normalized_path}", alt=alt, path=normalized_path)
   ```

2. **Frontend expects path URLs** (VisualizationGallery.tsx:29):
   ```tsx
   const src = attachment.path
     ? `/api/viz?path=${encodeURIComponent(attachment.path)}`
     : undefined;
   ```

3. **But endpoint doesn't exist:**
   ```bash
   $ grep -n "@app.get.*viz" agentspace/api/app.py
   # No results!
   ```

#### What Happens:
1. Tool generates heatmap → saves to `/plots/heatmap.png`
2. Tool returns metadata with `image_path: "/plots/heatmap.png"`
3. Extraction function creates attachment with `src: "/api/viz?path=/plots/heatmap.png"`
4. Frontend tries to load image from `/api/viz?path=...`
5. **404 Not Found** - Image never renders

### Secondary Issues

#### Issue 2: AgentScope Memory Format (Unconfirmed)

The extraction function assumes tool responses are stored in `agent.memory` with:
- `metadata` containing `viz_type`, `image_data`, etc.
- `content` containing ImageBlocks

**This might not be true** depending on how AgentScope stores tool responses.

#### Issue 3: No Debug Logging

The extraction function has no logging to help diagnose:
- Is memory being read?
- Are tool responses found?
- What format are they in?
- Are attachments being extracted?

#### Issue 4: Silent Failures

The extraction catches all exceptions and returns empty results:
```python
except Exception as exc:
    print(f"Warning: unable to read agent memory for visualizations: {exc}")
    return attachments, merged_metadata  # Returns empty!
```

If anything fails, visualizations silently disappear.

## Complete Fix

### Fix 1: Add `/api/viz` Endpoint (Required)

Add to `agentspace/api/app.py` after the existing endpoints (around line 760):

```python
from fastapi.responses import FileResponse
from pathlib import Path as FilePath
import os


@app.get("/api/viz")
def serve_visualization(path: str = Query(..., min_length=1)) -> FileResponse:
    """
    Serve visualization images from the plots directory.

    Security: Only serves files from the plots/ directory to prevent path traversal.
    """
    # Normalize and validate path
    requested_path = path.strip().replace("\\", "/")

    # Remove leading slashes
    while requested_path.startswith("/"):
        requested_path = requested_path[1:]

    # Resolve absolute path
    plots_dir = FilePath(__file__).parent.parent / "plots"
    file_path = (plots_dir / requested_path).resolve()

    # Security check: Ensure file is within plots directory
    try:
        file_path.relative_to(plots_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: Path outside plots directory")

    # Check file exists
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Visualization not found")

    # Determine content type
    content_type = "image/png"
    if file_path.suffix.lower() in (".jpg", ".jpeg"):
        content_type = "image/jpeg"
    elif file_path.suffix.lower() == ".svg":
        content_type = "image/svg+xml"

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
        }
    )
```

**Why this is needed:**
- Serves PNG/JPG files from the `plots/` directory
- Includes security checks to prevent path traversal attacks
- Returns proper content types
- Adds caching headers for performance

### Fix 2: Add Debug Logging (Recommended)

Update `_extract_tool_visualizations_from_memory` to add logging:

```python
import logging

logger = logging.getLogger(__name__)

async def _extract_tool_visualizations_from_memory(
    agent: ReActAgent,
    max_lookback: int = 12,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    merged_metadata: Dict[str, Any] = {}
    seen_sources: set[str] = set()

    try:
        history = await agent.memory.get_memory()
        logger.info(f"Reading agent memory: {len(history)} messages")  # ADD THIS
    except Exception as exc:
        logger.error(f"Failed to read agent memory: {exc}")  # ADD THIS
        return attachments, merged_metadata

    if not history:
        logger.warning("Agent memory is empty")  # ADD THIS
        return attachments, merged_metadata

    recent_messages = history[-max_lookback:]
    logger.info(f"Examining {len(recent_messages)} recent messages")  # ADD THIS

    viz_found = False  # ADD THIS

    for hist_msg in reversed(recent_messages):
        metadata = getattr(hist_msg, "metadata", None)
        content = getattr(hist_msg, "content", None)

        # ... existing code ...

        if isinstance(metadata, Mapping):
            if metadata.get("viz_type") or metadata.get("image_data") or metadata.get("images"):
                viz_found = True  # ADD THIS
                viz_type = metadata.get("viz_type", "unknown")
                logger.info(f"Found visualization: {viz_type}")  # ADD THIS

                # ... rest of extraction code ...

    if not viz_found:
        logger.warning("No visualizations found in agent memory")  # ADD THIS
    else:
        logger.info(f"Extracted {len(attachments)} attachments")  # ADD THIS

    return attachments, merged_metadata
```

### Fix 3: Ensure plots/ Directory Exists

Add to `agentspace/api/app.py` startup:

```python
@app.on_event("startup")
async def startup_event():
    """Ensure required directories exist."""
    plots_dir = Path(__file__).parent.parent / "plots"
    plots_dir.mkdir(exist_ok=True)
    logger.info(f"Plots directory: {plots_dir}")
```

### Fix 4: Verify Tool Registration

Ensure viz tools are registered when building the agent. Check `agentspace/agents/statsbomb_chat.py:370`:

```python
register_statsbomb_viz_tools(toolkit, group_name="statsbomb-viz", activate=True)
```

Should be present in both `build_chat_agent()` and `build_scouting_agent()`.

## Testing the Fix

### 1. Add the `/api/viz` Endpoint

```python
# Add to agentspace/api/app.py
```

### 2. Restart Backend

```bash
# Kill existing server
pkill -f "uvicorn.*agentspace"

# Start with logging
uvicorn agentspace.api.app:app --reload --log-level debug
```

### 3. Test with curl

```bash
# Create a test image
mkdir -p plots
echo "fake-png-data" > plots/test.png

# Test endpoint
curl http://localhost:8000/api/viz?path=test.png

# Should return file content, not 404
```

### 4. Test in Chat UI

1. Open chat: http://localhost:3000
2. Ask: *"Show me a heatmap for Arsenal in match 3869151"*
3. Check browser DevTools → Network tab
4. Look for requests to `/api/viz?path=...`
5. Verify they return 200, not 404

### 5. Check Logs

Watch backend logs for:
```
INFO:     Reading agent memory: 15 messages
INFO:     Examining 12 recent messages
INFO:     Found visualization: event_heatmap
INFO:     Extracted 1 attachments
```

## Debugging Steps if Still Not Working

### Step 1: Verify Tool is Called

Add to viz.py:193 (in `plot_event_heatmap_tool`):

```python
print(f"DEBUG: Generated heatmap at {result.path}")
print(f"DEBUG: Metadata: {metadata}")
```

Run chat request → Check logs for these print statements.

### Step 2: Inspect Agent Memory

Add temporary endpoint:

```python
@app.get("/api/debug/memory/{session_id}")
async def debug_memory(session_id: str):
    """DEBUG: Inspect agent memory"""
    session = _chat_sessions.get(session_id)
    if not session:
        return {"error": "Session not found"}

    history = await session.agent.memory.get_memory()
    return {
        "message_count": len(history),
        "messages": [
            {
                "role": getattr(msg, "role", None),
                "has_metadata": hasattr(msg, "metadata"),
                "metadata_keys": list(msg.metadata.keys()) if hasattr(msg, "metadata") and isinstance(msg.metadata, dict) else [],
                "has_content": hasattr(msg, "content"),
                "content_type": type(msg.content).__name__ if hasattr(msg, "content") else None,
            }
            for msg in history
        ]
    }
```

After chat request:
```bash
curl http://localhost:8000/api/debug/memory/<session-id>
```

Look for messages with `viz_type` in metadata_keys.

### Step 3: Check Extraction Output

Add before line 605 in agent_chat:

```python
print(f"DEBUG: tool_attachments = {tool_attachments}")
print(f"DEBUG: tool_metadata keys = {list(tool_metadata.keys())}")
```

### Step 4: Check Frontend Receipt

In ChatPanel.tsx:538, add:

```typescript
console.log("Agent response:", data);
console.log("Attachments:", attachments);
console.log("Metadata:", metadata);
```

Open browser console → Check what data frontend receives.

## Expected Behavior After Fix

### Backend Logs:
```
INFO:     Reading agent memory: 18 messages
INFO:     Examining 12 recent messages
INFO:     Found visualization: event_heatmap
INFO:     Extracted 1 attachments
INFO:     GET /api/viz?path=plots/heatmap_Arsenal_3869151.png
INFO:     Response: 200 OK
```

### Browser Network Tab:
```
GET /api/chat
  Status: 200
  Response: {
    "attachments": [
      {
        "type": "image",
        "src": "/api/viz?path=plots/heatmap_Arsenal_3869151.png",
        "alt": "event_heatmap"
      }
    ]
  }

GET /api/viz?path=plots/heatmap_Arsenal_3869151.png
  Status: 200
  Content-Type: image/png
```

### Chat UI:
```
[User message]
Show me a heatmap for Arsenal

[Agent response with text]
Created heatmap for Arsenal in match 3869151.
Events considered: Pass, Carry, Dribble (342 records).

[Rendered heatmap image showing colored pitch with density zones]
```

## Summary

### What Works ✅
- Memory extraction function implementation
- Attachment/metadata merging logic
- Frontend rendering component

### What's Missing ❌
- `/api/viz` endpoint to serve image files
- Debug logging to diagnose issues
- Startup validation for plots directory

### The Fix 🔧
1. **Add `/api/viz` endpoint** (5 minutes) - REQUIRED
2. **Add logging** (10 minutes) - Recommended
3. **Test thoroughly** (15 minutes) - Required
4. **Add debug endpoint** (5 minutes) - Optional but helpful

### Time to Fix
- **Minimal**: 10 minutes (just add `/api/viz` endpoint)
- **Complete**: 30 minutes (add endpoint + logging + testing)

## Next Steps

1. ✅ Add `/api/viz` endpoint to `agentspace/api/app.py`
2. ✅ Add import: `from fastapi.responses import FileResponse`
3. ✅ Restart backend server
4. ✅ Test with a heatmap request
5. ✅ Verify image renders in chat UI

Once you add the `/api/viz` endpoint, the visualizations should start rendering immediately!
