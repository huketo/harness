// Validation used by the members API (mirrored from the backend).
// name: string, 1..255, optional for invited members (they may only have an email)
// email: string, no max length enforced
// title: string, 0..120, optional
// status: 'active' | 'invited' | 'expired' | 'suspended'
// avatar: URL string, optional; uploads accept any aspect ratio
// lastActiveAt: epoch milliseconds, null when the member never signed in
window.MEMBER_SCHEMA = {
  name: { type: 'string', max: 255, optional: true },
  email: { type: 'string' },
  title: { type: 'string', max: 120, optional: true },
  status: { enum: ['active', 'invited', 'expired', 'suspended'] },
  avatar: { type: 'string', optional: true },
  lastActiveAt: { type: 'number', nullable: true },
};
