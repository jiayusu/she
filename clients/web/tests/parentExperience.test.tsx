// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { RootApp } from "@/features/RootApp";
import { AppModel, type RpgDemoIdentity } from "@/state/appModel";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
let root: Root;
let host: HTMLDivElement;
afterEach(() => {
  if (root) act(() => root.unmount());
  host?.remove();
});
const fixture = (name: string) =>
  JSON.parse(
    readFileSync(
      resolve("../../shared/contracts/v1/fixtures/valid", `${name}.json`),
      "utf8",
    ),
  );
async function mount(rpgDemoIdentity?: RpgDemoIdentity) {
  const constraints = {
    ...fixture("parent-constraints"),
    session_budget_seconds: 900,
    next_day_context: "周末公园",
    preferred_topics: ["dinosaurs"],
    avoid_topics: ["monsters"],
  };
  const api = {
    dashboard: async () => fixture("dashboard-snapshot"),
    weeklyReport: async () => fixture("weekly-report"),
    deviceSettings: async () => fixture("device-settings"),
    parentConstraints: async () => constraints,
    questState: vi.fn(async () => fixture("rpg-quest-summary")),
    updateParentConstraints: vi.fn(async (value) => ({
      ...constraints,
      ...value,
    })),
  };
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <RootApp
        model={new AppModel(
          api as never,
          rpgDemoIdentity === undefined ? {} : { rpgDemoIdentity },
        )}
      />,
    ),
  );
  return api;
}
async function click(text: string) {
  const button = [...host.querySelectorAll("button")].find((el) =>
    el.textContent?.includes(text),
  );
  expect(button, text).toBeTruthy();
  await act(async () => button!.click());
}
test("RPG card is absent when no demo identity is configured", async () => {
  const api = await mount();
  expect(api.questState).not.toHaveBeenCalled();
  expect(host.querySelector("[data-rpg-quest]")).toBeNull();
});
test("Today shows the current read-only embodied quest summary", async () => {
  const api = await mount({ childId: "child-demo", sessionId: "session-demo" });
  expect(api.questState).toHaveBeenCalledWith("child-demo", "session-demo");
  expect(host.querySelector("[data-rpg-quest]")).toBeTruthy();
  expect(host.textContent).toContain("当前现实语言任务 · 家长只读");
  expect(host.textContent).toContain("正在寻找现实线索");
  expect(host.textContent).toContain("杯子管理员");
  expect(host.textContent).toContain("I choose the red cup.");
  expect(host.textContent).toContain("牛奶（虚拟）");
  expect(host.textContent).toContain("在房间里找到红杯子");
  expect(host.textContent).toContain("等待发送到设备");
  expect(host.textContent).not.toContain("milk_ready");
});
test("home opens a child preview without parent controls and returns to home", async () => {
  await mount();
  await click("和孩子一起看");
  expect(host.querySelector("[data-child-preview]")).toBeTruthy();
  expect(host.querySelector("nav")).toBeNull();
  expect(host.textContent).not.toContain("无提示输出");
  await click("返回家长首页");
  expect(host.querySelector("nav")).toBeTruthy();
});
test("family form restores the server plan and preserves topics when saving", async () => {
  const api = await mount();
  await click("家庭计划");
  expect(
    (host.querySelector("#session-minutes") as HTMLInputElement).value,
  ).toBe("15");
  expect(
    (host.querySelector("#next-day-context") as HTMLInputElement).value,
  ).toBe("周末公园");
  await click("保存计划");
  expect(api.updateParentConstraints).toHaveBeenCalledWith(
    expect.objectContaining({
      preferred_topics: ["dinosaurs"],
      avoid_topics: ["monsters"],
      session_budget_seconds: 900,
    }),
  );
  await click("今天");
  await click("家庭计划");
  expect(
    (host.querySelector("#next-day-context") as HTMLInputElement).value,
  ).toBe("周末公园");
});
