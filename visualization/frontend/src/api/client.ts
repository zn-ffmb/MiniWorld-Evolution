import axios from "axios";
import type {
  BuildRequest,
  BuildResponse,
  EvolveRequest,
  EvolveResponse,
  WorldListResponse,
} from "../types/api";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

export async function startBuild(req: BuildRequest): Promise<BuildResponse> {
  const { data } = await api.post<BuildResponse>("/build", req);
  return data;
}

export async function startEvolve(req: EvolveRequest): Promise<EvolveResponse> {
  const { data } = await api.post<EvolveResponse>("/evolve", req);
  return data;
}

export async function listWorlds(): Promise<WorldListResponse> {
  const { data } = await api.get<WorldListResponse>("/worlds");
  return data;
}

export async function getWorld(worldId: string): Promise<any> {
  const { data } = await api.get(`/worlds/${worldId}`);
  return data;
}

export async function listEvolutions(worldId: string): Promise<any> {
  const { data } = await api.get(`/worlds/${worldId}/evolutions`);
  return data;
}
