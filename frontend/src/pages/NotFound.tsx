import { Link } from "react-router-dom";
import { LogoMark } from "@/components/brand";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-6 text-center">
      <LogoMark className="size-12" />
      <h1 className="mt-6 text-4xl">This page drifted away</h1>
      <p className="mt-3 max-w-sm text-muted-foreground">The link may be old, or the page may have moved.</p>
      <Button asChild className="mt-8">
        <Link to="/">Back to Folium</Link>
      </Button>
    </main>
  );
}
