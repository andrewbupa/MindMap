export const metadata = { title: "Signed out" };

export default function SignedOutPage() {
  return (
    <main style={{ maxWidth: "32rem", margin: "15vh auto", padding: "0 var(--space-5)" }}>
      <h1>You have signed out</h1>
      <p>
        <a href="/api/auth/login">Sign in again</a>
      </p>
    </main>
  );
}
