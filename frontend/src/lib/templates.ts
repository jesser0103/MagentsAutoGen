/**
 * Mission Template Library — local-storage backed template store.
 *
 * Templates let operators save common mission patterns and reload them
 * with a single click rather than retyping boilerplate requests.
 *
 * Built-in templates ship with the app. User-created templates are
 * persisted to localStorage under the key STORAGE_KEY.
 */

export interface MissionTemplate {
  id: string;
  name: string;
  description: string;
  request: string;
  category: 'networking' | 'compute' | 'storage' | 'security' | 'custom';
  builtIn?: boolean;
}

const STORAGE_KEY = 'magent:mission-templates';

// ---------------------------------------------------------------------------
// Built-in templates
// ---------------------------------------------------------------------------

export const BUILT_IN_TEMPLATES: MissionTemplate[] = [
  {
    id: 'tpl-aks-private',
    name: 'Private AKS Cluster',
    description: 'Provisions a private AKS cluster with CNI networking, RBAC, and Azure AD integration.',
    category: 'compute',
    builtIn: true,
    request:
      'Provision a private AKS cluster in West Europe with Azure CNI networking, ' +
      'Entra ID integration, node auto-provisioning enabled, system node pool of 3 nodes ' +
      '(Standard_D4s_v5), and environment/owner/cost_center tags set to prod/platform/infra-001.',
  },
  {
    id: 'tpl-storage-secure',
    name: 'Encrypted Blob Storage with Private Endpoints',
    description: 'Encrypted Azure Blob Storage with private endpoints and no public access.',
    category: 'storage',
    builtIn: true,
    request:
      'Create an Azure Storage Account in UK South with private endpoint only (no public access), ' +
      'minimum TLS 1.2, customer-managed key encryption via Key Vault, geo-redundant storage (GRS), ' +
      'soft delete enabled for blobs and containers (30 days), and environment/owner/cost_center tags.',
  },
  {
    id: 'tpl-vnet-hub',
    name: 'Azure Zero-Trust Virtual Network (Hub & Spoke)',
    description: 'Hub-and-spoke VNet with Azure Firewall Premium and DDoS protection.',
    category: 'networking',
    builtIn: true,
    request:
      'Deploy a hub VNet (10.0.0.0/16) in West Europe with Azure Firewall Premium in a dedicated ' +
      'AzureFirewallSubnet, DDoS Network Protection enabled, and a bastion host subnet. ' +
      'Include the standard environment/owner/cost_center tags.',
  },
  {
    id: 'tpl-postgres-geo-replication',
    name: 'PostgreSQL with Geo-Replication & PITR Backup',
    description: 'Private PostgreSQL with geo-replication and point-in-time restore backup.',
    category: 'storage',
    builtIn: true,
    request:
      'Create Azure Database for PostgreSQL Flexible Server in North Europe with private endpoint ' +
      'access only, geo-redundant backup, seven-day point-in-time restore, and a paired-region ' +
      'replica. Include environment/owner/cost_center tags.',
  },
  {
    id: 'tpl-python-api',
    name: 'Python Azure API helper',
    description: 'Python script that uses DefaultAzureCredential to call an Azure service.',
    category: 'compute',
    builtIn: true,
    request:
      'Write a Python script that uses DefaultAzureCredential to list all resource groups ' +
      'in a subscription and output their names and locations as JSON. ' +
      'Use the azure-mgmt-resource SDK and handle authentication errors gracefully.',
  },
];

// ---------------------------------------------------------------------------
// CRUD helpers
// ---------------------------------------------------------------------------

function loadCustom(): MissionTemplate[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MissionTemplate[]) : [];
  } catch {
    return [];
  }
}

function saveCustom(templates: MissionTemplate[]): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
}

export function listTemplates(): MissionTemplate[] {
  return [...BUILT_IN_TEMPLATES, ...loadCustom()];
}

export function saveTemplate(template: Omit<MissionTemplate, 'id' | 'builtIn'>): MissionTemplate {
  const saved: MissionTemplate = {
    ...template,
    id: `tpl-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    builtIn: false,
  };
  const existing = loadCustom().filter((t) => t.id !== saved.id);
  saveCustom([...existing, saved]);
  return saved;
}

export function deleteTemplate(id: string): void {
  const existing = loadCustom().filter((t) => t.id !== id);
  saveCustom(existing);
}
