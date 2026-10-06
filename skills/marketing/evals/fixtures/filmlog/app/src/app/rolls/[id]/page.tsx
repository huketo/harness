import type { Metadata } from 'next';
import { getRoll } from '@/lib/rolls';

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const roll = await getRoll(params.id);
  return { title: roll.title, description: `${roll.stock} · ${roll.camera}` };
}

export default async function RollPage({ params }: { params: { id: string } }) {
  const roll = await getRoll(params.id);
  return <article><h1>{roll.title}</h1></article>;
}
