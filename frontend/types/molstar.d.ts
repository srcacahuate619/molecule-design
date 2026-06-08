declare module "molstar/build/viewer/molstar.js" {
  export class Viewer {
    constructor(element: HTMLElement, options?: any);
    loadStructureFromData(data: string, format: string, options?: any): Promise<void>;
    loadAllFormats(url: string): Promise<void>;
    dispose(): void;
    resize(width?: number, height?: number): void;
  }
}

declare module "molstar/build/viewer/molstar.css";
