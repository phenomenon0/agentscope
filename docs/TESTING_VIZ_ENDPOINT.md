# Testing the /api/viz Endpoint

The `/api/viz` endpoint has been implemented to serve visualization images from the `plots/` directory.

## Quick Test

### Option 1: Using the Backend Server

1. **Start the backend server:**
   ```bash
   cd /Users/jethrovic/Documents/AGENTSPACE
   uvicorn agentspace.api.app:app --reload
   ```

2. **Test in browser:**
   Navigate to: http://localhost:8000/api/viz?path=test_viz.png

3. **Test with curl:**
   ```bash
   curl -I http://localhost:8000/api/viz?path=test_viz.png
   ```

   Expected output:
   ```
   HTTP/1.1 200 OK
   content-type: image/png
   cache-control: public, max-age=3600
   ```

### Option 2: Using Python Test Script

Run the manual test script:
```bash
python3 test_viz_endpoint_manual.py
```

This will verify:
- ✓ Basic image retrieval (200 response)
- ✓ Non-existent file handling (404 response)
- ✓ Path traversal protection (403/404 response)
- ✓ Cache headers present
- ✓ Endpoint listed in index

### Option 3: Using pytest (if installed)

```bash
pytest tests/test_api_viz_endpoint.py -v
```

## End-to-End Test with Chat

1. **Start backend:**
   ```bash
   uvicorn agentspace.api.app:app --reload
   ```

2. **Start frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Open browser:**
   Navigate to: http://localhost:3000

4. **Test visualization:**
   In the chat, ask:
   ```
   Show me a heatmap for Arsenal in match 3869151
   ```

5. **Verify:**
   - Agent should generate a heatmap
   - Image should appear in the chat UI
   - Browser DevTools → Network tab should show:
     - `GET /api/agent/chat` → 200
     - `GET /api/viz?path=plots/heatmap_...png` → 200

## Expected Behavior

### Successful Request
```bash
GET /api/viz?path=test_viz.png

Response:
  Status: 200 OK
  Content-Type: image/png
  Cache-Control: public, max-age=3600
  Body: <image binary data>
```

### File Not Found
```bash
GET /api/viz?path=nonexistent.png

Response:
  Status: 404 Not Found
  Content-Type: application/json
  Body: {"detail": "Visualization not found: nonexistent.png"}
```

### Path Traversal Blocked
```bash
GET /api/viz?path=../../etc/passwd

Response:
  Status: 403 Forbidden
  Content-Type: application/json
  Body: {"detail": "Access denied: Path outside plots directory"}
```

## Supported Image Formats

The endpoint automatically detects and serves:
- `.png` → `image/png`
- `.jpg`, `.jpeg` → `image/jpeg`
- `.svg` → `image/svg+xml`
- `.gif` → `image/gif`
- `.webp` → `image/webp`

## Security Features

1. **Path Traversal Protection:**
   - Only serves files from `plots/` directory
   - Rejects paths that escape the directory (e.g., `../../../etc/passwd`)

2. **File Validation:**
   - Verifies file exists before serving
   - Returns 404 for non-existent files

3. **Cache Headers:**
   - Sets `Cache-Control: public, max-age=3600`
   - Improves performance for frequently accessed images

## Troubleshooting

### Issue: 404 Not Found

**Cause:** File doesn't exist in `plots/` directory

**Solution:**
```bash
# Check if file exists
ls -la plots/

# Generate a test visualization
python3 -c "
from PIL import Image
img = Image.new('RGB', (400, 300), 'lightblue')
img.save('plots/test.png')
"
```

### Issue: 403 Forbidden

**Cause:** Path traversal detected

**Solution:** Ensure path is relative and within `plots/` directory
- ✓ Good: `heatmap.png`
- ✓ Good: `heatmaps/arsenal.png`
- ✗ Bad: `../config.py`
- ✗ Bad: `/etc/passwd`

### Issue: Empty plots/ directory

**Cause:** Visualizations not being generated

**Solution:**
1. Check agent is calling visualization tools
2. Check `output_dir` parameter in viz tools
3. Check backend logs for errors:
   ```bash
   tail -f backend.log | grep viz
   ```

### Issue: Image not rendering in chat

**Checklist:**
1. ✓ Backend running? (`http://localhost:8000/api/health`)
2. ✓ Frontend running? (`http://localhost:3000`)
3. ✓ `/api/viz` endpoint working? (Test with curl)
4. ✓ Image file exists? (`ls plots/`)
5. ✓ Browser console for errors? (F12 → Console)
6. ✓ Network tab shows request? (F12 → Network)

## Backend Logs

When working correctly, you should see:
```
INFO:     Application startup complete.
✓ Plots directory: /Users/jethrovic/Documents/AGENTSPACE/plots
INFO:     127.0.0.1:52000 - "GET /api/viz?path=test_viz.png HTTP/1.1" 200 OK
```

## Files Modified

- ✅ `agentspace/api/app.py` - Added `/api/viz` endpoint
- ✅ `agentspace/api/app.py` - Added startup event for plots directory
- ✅ `tests/test_api_viz_endpoint.py` - Added comprehensive tests
- ✅ `test_viz_endpoint_manual.py` - Added manual test script

## Next Steps

1. ✅ Commit changes
2. ✅ Push to GitHub
3. ⏭️ Restart backend server
4. ⏭️ Test with real heatmap generation
5. ⏭️ Verify images render in chat UI

## Success Criteria

✅ Endpoint returns 200 for valid images
✅ Endpoint returns 404 for missing files
✅ Endpoint returns 403 for path traversal attempts
✅ Endpoint sets correct content-type headers
✅ Endpoint sets cache headers
✅ Images render in chat UI when agent generates visualizations
