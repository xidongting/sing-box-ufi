declare function runShellWithRoot(command: string, timeout?: number): Promise<{success: boolean; content: string}>;
declare function showModal(selector: string): void;
declare function createModal(options: {
    name: string; title: string; maxWidth: string; showConfirm: boolean;
    onClose: () => boolean; content: string;
}): {el: HTMLElement; id: string} | undefined;
