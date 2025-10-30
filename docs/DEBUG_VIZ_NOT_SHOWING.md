# Debugging: Why Visualizations Aren't Showing

## Current Status

### ✅ What's Working

1. **`/api/viz` Endpoint**: ✅ WORKING
   ```bash
   curl "http://localhost:8001/api/viz?path=test_viz.png"
   # Returns PNG binary data - SUCCESS
   ```

2. **Visualization Generation**: ✅ WORKING
   ```bash
   ls -la plots/
   # Shows 17 files including:
   # - heatmap_match-3956004_liverpool_pass-carry-dribble.png
   # - pass-network_match-3956008_arsenal.png
   # - shot-map_match-4004256_all.png
   ```

3. **Backend Server**: ✅ RUNNING
   - Port 8001
   - Auto-reload enabled

### ❓ What's Unknown

We need to check:
1. Is the agent adding visualization data to its responses?
2. Is the memory extraction finding the tool responses?
3. Is the frontend receiving the attachments?
4. Is the frontend correctly rendering the attachments?

## Debug Steps

### Step 1: Check Backend Logs

I've added debug logging to the backend. When you make a chat request that generates a visualization, watch the terminal for:

```
DEBUG: Extracted X tool attachments
DEBUG: Tool metadata keys: [...]
DEBUG: Attachment 0: type=image, src=...
DEBUG: Returning X total attachments
DEBUG: Final metadata has viz_type: ...
```

**Expected output if working:**
```
DEBUG: Extracted 1 tool attachments
DEBUG: Tool metadata keys: ['viz_type', 'team_name', 'match_id', ...]
DEBUG: Attachment 0: type=image, src=/api/viz?path=plots/heatmap_...
DEBUG: Returning 1 total attachments
DEBUG: Final metadata has viz_type: event_heatmap
```

**If you see 0 attachments**, the memory extraction isn't finding the viz data.

### Step 2: Test a Simple Request

Make this request in the chat:
```
Show me a heatmap for Liverpool
```

The agent should:
1. Call `plot_event_heatmap_tool`
2. Generate a PNG file in `plots/`
3. Return metadata with image data
4. Memory extraction should find it
5. Response should include attachments

### Step 3: Check Frontend Console

Open browser DevTools (F12) → Console tab.

Look for:
```javascript
Agent response: {...}
Attachments: [...]
Metadata: {...}
```

This will show what the frontend actually received.

### Step 4: Check Network Tab

Open browser DevTools (F12) → Network tab.

Look for:
1. `POST /api/agent/chat` → Should return 200
   - Check Response tab → Look for `attachments` array
   - Should have objects with `src: "/api/viz?path=..."`

2. `GET /api/viz?path=...` → Should return 200
   - Check Preview tab → Should show image
   - Check Headers → `content-type: image/png`

## Common Issues

### Issue 1: No Attachments in Response

**Symptom:**
```
DEBUG: Extracted 0 tool attachments
DEBUG: Returning 0 total attachments
```

**Possible causes:**
1. Agent didn't call visualization tool
2. Tool didn't add metadata correctly
3. Memory extraction can't find the tool response
4. Tool response format doesn't match expectations

**Fix:** Check agent memory format

### Issue 2: Attachments Present, But Images Don't Render

**Symptom:**
- Backend logs show attachments
- Frontend receives attachments
- Images still don't appear

**Possible causes:**
1. Frontend path construction wrong
2. CORS issue
3. Image component not rendering
4. CSS hiding images

**Fix:** Check browser console for errors

### Issue 3: Wrong Path Format

**Symptom:**
```javascript
attachments: [{
  src: "/plots/heatmap.png"  // Missing /api/viz prefix
}]
```

**Fix:** Check extraction function constructs correct URLs

## Quick Test Script

Run this to test the full flow:

```python
import requests
import json

# 1. Make a chat request
response = requests.post("http://localhost:8001/api/agent/chat", json={
    "persona": "Analyst",
    "message": "Show me a heatmap for Liverpool in match 3956004"
})

data = response.json()

# 2. Check response
print(f"Status: {response.status_code}")
print(f"Has attachments: {bool(data.get('attachments'))}")
print(f"Attachment count: {len(data.get('attachments', []))}")

if data.get('attachments'):
    for i, att in enumerate(data['attachments']):
        print(f"\nAttachment {i}:")
        print(f"  Type: {att.get('type')}")
        print(f"  Src: {att.get('src')}")

        # Try to fetch the image
        if att.get('src', '').startswith('/api/viz'):
            img_url = f"http://localhost:8001{att['src']}"
            img_response = requests.get(img_url)
            print(f"  Image status: {img_response.status_code}")
            print(f"  Content-Type: {img_response.headers.get('content-type')}")
            print(f"  Size: {len(img_response.content)} bytes")

# 3. Print metadata
print(f"\nMetadata keys: {list(data.get('metadata', {}).keys())}")
print(f"Has viz_type: {bool(data.get('metadata', {}).get('viz_type'))}")
```

Save as `test_viz_flow.py` and run:
```bash
python3 test_viz_flow.py
```

## What to Do Next

1. **Restart backend** to pick up debug logging:
   ```bash
   # Kill existing server
   pkill -f "uvicorn.*agentspace"

   # Start with visible output
   uvicorn agentspace.api.app:app --reload --port 8001
   ```

2. **Make a test request** that should generate a visualization

3. **Check the DEBUG output** to see where it breaks

4. **Report back** with:
   - What the DEBUG logs show
   - What the frontend console shows
   - What the Network tab shows

Then I can pinpoint the exact issue and fix it!

## Hypothesis

Based on the code, my best guess is one of these:

**Hypothesis A**: Memory extraction isn't finding tool responses because AgentScope stores them in a different format than expected.

**Hypothesis B**: Tool responses ARE in memory but the metadata structure doesn't match what we're looking for (e.g., checking for `viz_type` but it's stored as something else).

**Hypothesis C**: Everything works but there's a frontend rendering issue (less likely since VisualizationGallery looks correct).

The DEBUG logs will tell us which hypothesis is correct!
