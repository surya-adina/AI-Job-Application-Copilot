const API_URL = process.env.NEXT_PUBLIC_API_URL!;

export default async function Home(){
  const res = await fetch(API_URL, {cache: "no-store"});
  const text = await res.text();

  return (
    <main className = "p-8">
      <h1 className="text-2xl font bold">AI Job Search Copilot</h1>
      <p className="mt-4">Backend says: {text}</p>
    </main>
  )

}