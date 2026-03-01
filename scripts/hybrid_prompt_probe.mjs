#!/usr/bin/env node
import { chromium } from "playwright";

function arg(name, fallback = "") {
  const i = process.argv.indexOf(name);
  if (i === -1 || i + 1 >= process.argv.length) return fallback;
  return process.argv[i + 1];
}

const url = arg("--url", "http://localhost:8087");
const prompt = arg("--prompt", "");
const timeoutMs = Number(arg("--timeout-ms", "120000"));

if (!prompt) {
  console.error("ERROR: --prompt is required");
  process.exit(2);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const watchdog = setTimeout(() => {
  console.error(`PROBE_WATCHDOG_TIMEOUT after ${timeoutMs + 30000}ms`);
  process.exit(3);
}, timeoutMs + 30000);

try {
  const log = (m) => console.error(`[probe] ${m}`);
  const baseOrigin = new URL(url).origin;
  await page.setExtraHTTPHeaders({ Referer: url, Origin: baseOrigin });
  log("prime csrf");
  try {
    const csrfRes = await page.request.get(`${baseOrigin}/csrf_token`, {
      headers: { Referer: url, Origin: baseOrigin },
      timeout: 15000,
    });
    const csrfText = await csrfRes.text();
    log(`csrf status=${csrfRes.status()}`);
    const parsed = JSON.parse(csrfText);
    if (parsed?.ok && parsed?.token && parsed?.runtime_id) {
      await page.context().addCookies([
        {
          name: `csrf_token_${parsed.runtime_id}`,
          value: parsed.token,
          url: baseOrigin,
        },
      ]);
      log("csrf cookie primed");
    }
  } catch (err) {
    log(`csrf prime skipped: ${err instanceof Error ? err.message : String(err)}`);
  }

  log("goto");
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
  await page
    .waitForFunction(
      () =>
        (document.body?.innerText || "").includes("Chats") &&
        (document.body?.innerText || "").includes("Tasks"),
      { timeout: 20000 }
    )
    .catch(() => {});
  const openedChat = await page.evaluate(() => {
    const iconLike = new Set([
      "edit_square",
      "add_circle",
      "folder",
      "memory",
      "schedule",
      "settings",
      "folder_open",
      "language",
      "code",
      "refresh",
      "info",
      "close",
    ]);
    const newChatEl = Array.from(document.querySelectorAll("*")).find((el) => {
      const txt = (el.textContent || "").replace(/\s+/g, " ").trim();
      return (
        (txt === "New Chat" || txt.endsWith(" New Chat")) &&
        window.getComputedStyle(el).cursor === "pointer"
      );
    });
    if (newChatEl) {
      newChatEl.click();
      return "clicked:New Chat";
    }

    const lines = (document.body?.innerText || "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const chatsIdx = lines.indexOf("Chats");
    const tasksIdx = lines.indexOf("Tasks");
    if (chatsIdx === -1 || tasksIdx === -1 || tasksIdx <= chatsIdx) return "chat-list-not-found";
    const target = lines
      .slice(chatsIdx + 1, tasksIdx)
      .find(
        (line) =>
          !iconLike.has(line) &&
          line !== "New Chat" &&
          !line.startsWith("{") &&
          !line.includes("[") &&
          !line.includes(":")
      );
    if (!target) return "no-chat-target";
    const clickable = Array.from(document.querySelectorAll("*")).find((el) => {
      const txt = (el.textContent || "").replace(/\s+/g, " ").trim();
      return (
        txt === target &&
        window.getComputedStyle(el).cursor === "pointer"
      );
    });
    if (!clickable) return `target-not-clickable:${target}`;
    clickable.click();
    return `clicked:${target}`;
  });
  log(`open-chat: ${openedChat}`);

  log("capture prior stub markers");
  const beforeBodyText = await page.locator("body").innerText();
  const beforeMatches = beforeBodyText.match(/\[stub-ollama\][^\n]*/g) || [];
  const beforeCount = beforeMatches.length;

  log("try alpine send");
  const alpineSend = await page.evaluate((text) => {
    const alpine = window.Alpine;
    if (!alpine || typeof alpine.store !== "function") return "no-alpine";
    const store = alpine.store("chatInput");
    if (!store || typeof store.sendMessage !== "function") return "no-chat-store";
    store.message = text;
    store.sendMessage();
    return "sent";
  }, prompt);
  log(`alpine-send-result: ${alpineSend}`);

  if (alpineSend !== "sent") {
    log("ensure chat composer");
    const input = page.locator("textarea#chat-input").first();
    const send = page.locator("button[aria-label='Send message'], button.chat-button").first();
    const openResult = await page.evaluate(() => {
      const isVisible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      };
      const isComposerVisible = () => {
        const textarea = document.querySelector("textarea#chat-input");
        const sendBtn =
          document.querySelector("button[aria-label='Send message']") ||
          Array.from(document.querySelectorAll("button")).find((b) =>
            (b.textContent || "").trim().toLowerCase() === "send"
          );
        return isVisible(textarea) && isVisible(sendBtn);
      };
      if (isComposerVisible()) return "already-visible";
      const clicks = [];
      const genericNewChat = Array.from(document.querySelectorAll("*")).filter((el) => {
        const t = (el.textContent || "").replace(/\s+/g, " ").trim();
        return t === "New Chat" || t.endsWith(" New Chat");
      });
      const candidates = [
        ...Array.from(document.querySelectorAll(".chat-list-button")),
        ...Array.from(document.querySelectorAll("button[aria-label='New Chat']")),
        ...Array.from(document.querySelectorAll("button")).filter((b) =>
          (b.textContent || "").replace(/\s+/g, " ").includes("New Chat")
        ),
        ...genericNewChat,
      ];
      for (const el of candidates) {
        try {
          el.click();
          clicks.push((el.className || el.tagName).toString());
        } catch {}
        if (isComposerVisible()) return `opened-after-${clicks.length}-clicks`;
      }
      return `not-opened clicks=${clicks.length}`;
    });
    log(`open-result: ${openResult}`);

    await page.waitForFunction(() => {
      const isVisible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      };
      const textarea = document.querySelector("textarea#chat-input");
      const sendBtn =
        document.querySelector("button[aria-label='Send message']") ||
        Array.from(document.querySelectorAll("button")).find(
          (b) => (b.textContent || "").trim().toLowerCase() === "send"
        );
      return isVisible(textarea) && isVisible(sendBtn);
    }, { timeout: timeoutMs });
    log("composer ready");

    try {
      log("set prompt value");
      await input.evaluate((el, text) => {
        el.focus();
        el.value = text;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      }, prompt);
      log("click send button");
      await send.click({ timeout: timeoutMs });
    } catch {
      log("fill/click fallback path");
      await input.click({ timeout: 5000 });
      await input.fill(prompt, { timeout: 5000 });
      await page.keyboard.press("Enter");
    }
  }

  const nudge = page.locator("button:has-text('Nudge')").first();

  let promptVisible = await page
    .waitForFunction((needle) => (document.body?.innerText || "").includes(needle), prompt, { timeout: 15000 })
    .then(() => true)
    .catch(() => false);
  if (!promptVisible) {
    log("retry prompt submit via visible composer");
    const visibleInput = page.locator("textarea#chat-input:visible").first();
    const visibleSend = page
      .locator("button[aria-label='Send message']:visible, button.chat-button:visible")
      .first();
    await visibleInput.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
    await visibleInput.fill(prompt, { timeout: 10000 }).catch(() => {});
    if (await visibleSend.count()) {
      await visibleSend.click({ timeout: 5000 }).catch(() => {});
    } else {
      await page.keyboard.press("Enter").catch(() => {});
    }
    promptVisible = await page
      .waitForFunction((needle) => (document.body?.innerText || "").includes(needle), prompt, { timeout: 15000 })
      .then(() => true)
      .catch(() => false);
  }
  log(`prompt-visible=${promptVisible}`);
  if (!promptVisible) {
    throw new Error("Prompt was not posted to the chat UI.");
  }

  log(`wait for new stub marker (before=${beforeCount})`);
  const promptAnchor = (prompt.match(/HYBRID_SHARED_TOKEN_[A-Za-z0-9_:-]+/) || [prompt])[0];
  const deadline = Date.now() + timeoutMs;
  let matched = false;
  let matchedLine = "";
  let lastNudgeAt = 0;
  while (Date.now() < deadline) {
    const bodyNow = await page.locator("body").innerText();
    const nowMatches = bodyNow.match(/\[stub-ollama\][^\n]*/g) || [];
    if (nowMatches.length > beforeCount) {
      const delta = nowMatches.slice(beforeCount);
      const relevant = delta.filter((line) => line.includes(promptAnchor) || line.includes(prompt));
      if (relevant.length > 0) {
        matchedLine = relevant[relevant.length - 1];
        matched = true;
        break;
      }
    }

    const now = Date.now();
    if (now - lastNudgeAt >= 10000 && (await nudge.count())) {
      log("click nudge fallback");
      await nudge.click({ timeout: 3000 }).catch(() => {});
      lastNudgeAt = now;
    }
    await page.waitForTimeout(3000);
  }
  if (!matched) {
    throw new Error("Timed out waiting for stub marker after prompt submission.");
  }

  log("extract body");
  const bodyText = await page.locator("body").innerText({ timeout: timeoutMs });
  const matches = bodyText.match(/\[stub-ollama\][^\n]*/g) || [];
  if (!matches.length) {
    throw new Error("No stub response found in page text.");
  }
  log("success");
  console.log((matchedLine || matches[matches.length - 1]).trim());
} catch (err) {
  const slug = new Date().toISOString().replace(/[:.]/g, "-");
  const path = `artifacts/e2e-hybrid/probe-failure-${slug}.png`;
  await page.screenshot({ path, fullPage: true }).catch(() => {});
  const text = await page.locator("body").innerText().catch(() => "");
  console.error(`PROBE_FAILURE: ${err instanceof Error ? err.message : String(err)}`);
  if (text) {
    console.error("PROBE_BODY_PREVIEW_START");
    console.error(text.slice(0, 2000));
    console.error("PROBE_BODY_PREVIEW_END");
  }
  console.error(`PROBE_SCREENSHOT=${path}`);
  process.exit(1);
} finally {
  clearTimeout(watchdog);
  await browser.close();
}
