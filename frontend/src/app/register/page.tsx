import Link from 'next/link';
import { RegisterForm } from './register-form';

export default function RegisterPage() {
  return (
    <main className="min-h-screen bg-background px-6 py-12 text-foreground">
      <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center">
        <div className="rounded-3xl border bg-card p-8 shadow-sm">
          <div className="mb-8">
            <p className="text-sm font-medium text-muted-foreground">
              AI Job Application Copilot
            </p>
            <h1 className="mt-2 text-3xl font-bold">Create your account</h1>
            <p className="mt-3 text-sm text-muted-foreground">
              Save resumes, create job applications, and generate AI-powered
              application materials.
            </p>
          </div>

          <RegisterForm />

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link href="/login" className="font-medium text-foreground underline">
              Log in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
