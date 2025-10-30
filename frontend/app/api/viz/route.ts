"use server";

import fs from "fs/promises";
import path from "path";
import mime from "mime";
import { NextRequest, NextResponse } from "next/server";

const WORKSPACE_ROOT = process.cwd();
const KNOWN_PREFIXES = [
  "plots",
  ".cache/offline_index",
];

async function resolveImagePath(rawPath: string): Promise<string | null> {
  const normalized = rawPath.replace(/\\/g, "/");
  if (normalized.startsWith("http://") || normalized.startsWith("https://")) {
    // Remote path—not served by this endpoint.
    return null;
  }

  for (const prefix of KNOWN_PREFIXES) {
    const candidate = path.join(WORKSPACE_ROOT, prefix, normalized);
    try {
      const stat = await fs.stat(candidate);
      if (stat.isFile()) {
        return candidate;
      }
    } catch {
      // try next prefix
    }
  }

  // Fallback: treat as workspace-relative
  const fallback = path.join(WORKSPACE_ROOT, normalized);
  try {
    const stat = await fs.stat(fallback);
    if (stat.isFile()) {
      return fallback;
    }
  } catch {
    return null;
  }
  return fallback;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const rawPath = searchParams.get("path");
  if (!rawPath) {
    return NextResponse.json({ error: "Missing `path` query parameter." }, { status: 400 });
  }

  const resolved = await resolveImagePath(rawPath);
  if (!resolved) {
    return NextResponse.json({ error: "Image not found." }, { status: 404 });
  }

  try {
    const buffer = await fs.readFile(resolved);
    const contentType = mime.getType(resolved) || "application/octet-stream";
    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=60",
      },
    });
  } catch (error) {
    console.error("Failed to read visualization:", error);
    return NextResponse.json({ error: "Failed to read visualization." }, { status: 500 });
  }
}
