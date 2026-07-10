import { createWorkspaceApplication } from './application/createWorkspaceApplication'
import { httpWorkspaceGateway } from './infrastructure/http/agentApi'
import { browserWorkspacePreferences } from './infrastructure/storage/workspaceStore'

export const workspaceApplication = createWorkspaceApplication(
  httpWorkspaceGateway,
  browserWorkspacePreferences,
)
