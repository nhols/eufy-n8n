const ts = () => new Date().toISOString();
export const log = (...args) => console.log(`[${ts()}]`, ...args);
