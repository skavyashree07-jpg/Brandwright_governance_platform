import { ProductPage } from "@/components/ProductPages";

export default async function SubmissionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProductPage page="submission" id={id} />;
}
