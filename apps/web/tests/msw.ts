import { setupServer } from "msw/node";

export const API = "http://localhost:8000/api/v1";
export const server = setupServer();
