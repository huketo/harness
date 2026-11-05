// Demo data for the members panel preview.
// Shape matches GET /api/workspaces/:id/members (see schema.js).
window.DEMO_WORKSPACE = {
  name: 'Acme Design',
  seatLimit: 25,
  members: [
    {
      id: 'm1',
      name: 'Mina Park',
      email: 'mina@example.com',
      title: 'Product Designer',
      status: 'active',
      avatar: 'avatars/mina.svg',
      lastActiveAt: Date.now() - 2 * 86400000,
    },
    {
      id: 'm2',
      name: 'Tom Lee',
      email: 'tom@example.com',
      title: 'Engineer',
      status: 'active',
      avatar: 'avatars/tom.svg',
      lastActiveAt: Date.now() - 5 * 86400000,
    },
    {
      id: 'm3',
      name: 'Sara Kim',
      email: 'sara@example.com',
      title: 'Marketing',
      status: 'invited',
      avatar: 'avatars/sara.svg',
      lastActiveAt: Date.now() - 3 * 86400000,
    },
  ],
};
