/**
 * A stand-in for the Sigma renderer, for tests that exercise code paths which
 * construct one (`TreeViewer.rerender`, the config bootstrap).
 *
 * Sigma needs a real WebGL context, which jsdom cannot provide, so any test
 * touching `setTree`/`rerender` would otherwise die in `createWebGLContext`.
 * Nothing here renders: it satisfies the surface the viewer and operators call,
 * so the *wiring* under test (events, reducers, operator attachment) runs
 * normally. Rendering correctness needs a browser and is out of scope for unit
 * tests.
 *
 * Use with `vi.mock("sigma", async () => await import("../test_support/fake_sigma"))`.
 */
export default class FakeSigma {
  constructor(
    private graph: unknown,
    private container: unknown,
    private settings: unknown
  ) {}

  /**
   * Registered handlers, so a test can drive the Sigma → viewer wiring (which
   * would otherwise be untestable: the real renderer only emits from gestures
   * on a WebGL canvas). Use {@link FakeSigma.emit} to fire one.
   */
  private handlers = new Map<string, Array<(payload: unknown) => void>>();

  on(event?: string, handler?: (payload: unknown) => void): void {
    if (!event || !handler) return;
    const list = this.handlers.get(event) ?? [];
    list.push(handler);
    this.handlers.set(event, list);
  }
  off(event?: string, handler?: (payload: unknown) => void): void {
    if (!event) return;
    if (!handler) return void this.handlers.delete(event);
    const list = (this.handlers.get(event) ?? []).filter((h) => h !== handler);
    this.handlers.set(event, list);
  }
  removeAllListeners(): void {
    this.handlers.clear();
  }

  /** Test-only: invoke every handler registered for `event`. */
  emit(event: string, payload: unknown): void {
    for (const h of this.handlers.get(event) ?? []) h(payload);
  }
  refresh(): void {}
  /** Real Sigma re-measures its container here; the viewer calls it on resize. */
  resize(): void {}
  kill(): void {}
  setSetting(): void {}
  getSetting(): undefined {
    return undefined;
  }

  getGraph(): unknown {
    return this.graph;
  }
  getContainer(): unknown {
    return this.container;
  }

  /**
   * Camera state, held rather than fabricated per call.
   *
   * It used to return a fresh `{x: 0.5, …}` every time and swallow `setState`,
   * which made any camera behaviour untestable — a pan and a no-op looked
   * identical. The recentring guard is exactly that kind of behaviour, so the
   * fake has to remember what it was told.
   */
  cameraState: { x: number; y: number; angle: number; ratio: number } = {
    x: 0.5,
    y: 0.5,
    angle: 0,
    ratio: 1,
  };

  /** Test-only: every `setState` the code under test issued, in order. */
  cameraWrites: Array<{ x: number; y: number; angle: number; ratio: number }> = [];

  getCamera() {
    return {
      getState: () => ({ ...this.cameraState }),
      setState: (state: { x: number; y: number; angle: number; ratio: number }) => {
        this.cameraState = { ...this.cameraState, ...state };
        this.cameraWrites.push({ ...this.cameraState });
      },
      animate: (_state: unknown, _opts: unknown, cb?: () => void) => cb?.(),
    };
  }

  getMouseCaptor() {
    return { on: () => {}, off: () => {} };
  }

  graphToViewport(coords: { x: number; y: number }) {
    return coords;
  }
  /**
   * Pixels per framed-graph unit. Settable because the recentring maths divides
   * by it, so a test needs to choose whether a given reserve lands above or
   * below the half-pixel threshold.
   */
  framedScale = 100;

  framedGraphToViewport(coords: { x: number; y: number }) {
    return { x: coords.x * this.framedScale, y: coords.y * this.framedScale };
  }
  getNodeDisplayData(): undefined {
    return undefined;
  }
}
