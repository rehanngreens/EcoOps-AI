import "@testing-library/jest-dom/vitest";

// jsdom lacks ResizeObserver, which Recharts requires.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
