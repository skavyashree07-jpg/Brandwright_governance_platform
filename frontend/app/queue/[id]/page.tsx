import { ProductPage } from "@/components/ProductPages";

export default async function QueueItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProductPage page="review" id={id} />;
}
