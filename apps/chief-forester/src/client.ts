import { RayfinClient } from '@microsoft/rayfin-client';
import { ensureSignedInWithFabric } from '@microsoft/rayfin-auth-provider-fabric';

import type { ChiefForesterSchema } from '../rayfin/data/schema';

export const client = new RayfinClient<ChiefForesterSchema>({
  baseUrl: import.meta.env.VITE_RAYFIN_API_URL ?? 'http://localhost:5168',
  publishableKey: import.meta.env.VITE_RAYFIN_PUBLISHABLE_KEY,
});

const fabricOptions = {
  workspaceId: import.meta.env.VITE_FABRIC_WORKSPACE_ID,
  projectId: import.meta.env.VITE_FABRIC_ITEM_ID,
  fabricPortalUrl: import.meta.env.VITE_FABRIC_PORTAL_URL ?? 'https://app.fabric.microsoft.com',
  returnOrigin: window.location.origin,
};

/**
 * Sign in with Fabric SSO when the app is deployed, fall back to email and
 * password locally.
 *
 * The fallback exists so the dashboard can be demonstrated before the Fabric
 * Apps workload is enabled in a tenant, which during a workshop is most of the
 * room. It is disabled in `rayfin.yml` for any environment you would call
 * production.
 */
export async function signIn(): Promise<{ email?: string; mode: 'fabric' | 'local' }> {
  const deployed = Boolean(fabricOptions.workspaceId && fabricOptions.projectId);

  if (deployed) {
    const session = await ensureSignedInWithFabric(client.auth, fabricOptions);
    return { email: session.user?.email, mode: 'fabric' };
  }

  const email = import.meta.env.VITE_LOCAL_USER ?? 'forester@localhost';
  const password = import.meta.env.VITE_LOCAL_PASSWORD ?? 'local-dev-only';
  await client.auth.signIn({ email, password });
  return { email, mode: 'local' };
}
