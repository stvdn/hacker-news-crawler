import { expect, test } from "@playwright/test";
import { testApiUrl as api } from "../test-config";

test.beforeEach(async ({ request }) => {
  await request.post(`${api}/__test/scenario`, { data: {} });
});

test("three views preserve ranks, boundaries, ordering, and usage", async ({ page, request }, testInfo) => {
  await page.goto("/");
  const rows = page.locator("tbody tr");
  const ranks = () => page.locator("tbody tr td:first-child").allTextContents();
  await expect(rows).toHaveCount(30);
  expect(await ranks()).toEqual(Array.from({ length: 30 }, (_, i) => String(i + 1)));
  await expect(page.getByText("30 of 30 stories")).toBeVisible();
  await expect(page.locator("time")).toHaveAttribute("datetime", "2026-10-02T12:00:00Z");
  await expect(rows.nth(4)).toContainText("C++ & Python: café <tools>");
  await expect(rows.nth(4).locator("td.metric")).toHaveText(["0", "0"]);
  await expect(rows.nth(5).locator("td.metric")).toHaveText(["—", "—"]);
  await page.screenshot({ path: testInfo.outputPath("stories.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  const long = page.getByRole("link", { name: "Long titles", exact: true });
  await long.hover();
  // A hover and an idle page must not prefetch another view or record usage.
  await page.waitForTimeout(600);
  expect(await (await request.get(`${api}/__test/events`)).json()).toHaveLength(1);
  await long.click();
  await expect(rows).toHaveCount(3);
  expect(await ranks()).toEqual(["2", "3", "4"]);
  await expect(long).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("columnheader", { name: "Comments" })).toHaveAttribute("aria-sort", "descending");
  await expect(page.getByRole("rowheader", { name: "One two three four five", exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "Short titles", exact: true }).click();
  await expect(rows).toHaveCount(27);
  expect(await ranks()).toEqual(["1", ...Array.from({ length: 24 }, (_, i) => String(30 - i)), "5", "6"]);
  await expect(page.getByRole("rowheader", { name: "One two three four five", exact: true })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "One two three four five six", exact: true })).toHaveCount(0);

  // Returning to a previous filter and selecting it again both reach FastAPI.
  await page.getByRole("link", { name: "All stories", exact: true }).click();
  await expect(rows).toHaveCount(30);
  await page.getByRole("link", { name: "All stories", exact: true }).click();
  await expect(rows).toHaveCount(30);
  const events = await (await request.get(`${api}/__test/events`)).json();
  expect(events.map((event: { filter: string }) => event.filter)).toEqual(["all", "long", "short", "all", "all"]);
});

for (const [status, message] of [
  [502, "Hacker News could not be read."],
  [503, "Usage recording is temporarily unavailable."],
  [504, "Hacker News took too long to respond."],
] as const) {
  test(`safe ${status} error and successful retry`, async ({ page, request }) => {
    await request.post(`${api}/__test/scenario`, { data: { status } });
    await page.goto("/?filter=long");
    await expect(page.getByRole("main").getByRole("alert")).toContainText(message);
    await expect(page.getByRole("main").getByRole("alert")).toContainText("Request ID:");
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.getByText("Synthetic", { exact: false })).toHaveCount(0);
    await request.post(`${api}/__test/scenario`, { data: {} });
    await page.getByRole("link", { name: "Try again" }).click();
    await expect(page.locator("tbody tr")).toHaveCount(3);
    await expect(page.getByRole("link", { name: "Long titles", exact: true })).toHaveAttribute("aria-current", "page");
  });
}

test("loading, empty results, and invalid URLs", async ({ page, request }) => {
  await request.post(`${api}/__test/scenario`, { data: { delay: 2, all_long_titles: true } });
  await page.goto("/?filter=short", { waitUntil: "commit" });
  await expect(page.getByRole("status")).toContainText("Loading stories");
  await expect(page.getByRole("heading", { name: "No matching stories" })).toBeVisible();
  await expect(page.getByText("0 of 30 stories")).toBeVisible();
  const [event] = await (await request.get(`${api}/__test/events`)).json();
  expect(event.filter).toBe("short");
  expect(event.result_count).toBe(0);
  await request.post(`${api}/__test/scenario`, { data: {} });
  for (const query of ["invalid", "all&filter=short"]) {
    await page.goto(`/?filter=${query}`);
    await expect(page.getByRole("main").getByRole("alert")).toContainText("Unknown filter");
  }
  expect(await (await request.get(`${api}/__test/events`)).json()).toHaveLength(0);
});

test("filters can be reached and activated with the keyboard", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to stories" })).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "All stories", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.locator("tbody tr")).toHaveCount(3);
});
