/// <reference types="vite/client" />

declare module "*.yaml?raw" {
  const content: string;
  export default content;
}

declare module "*.tf?raw" {
  const content: string;
  export default content;
}
