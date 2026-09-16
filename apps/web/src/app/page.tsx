export default function HomePage() {
  return (
    <div className="max-w-[40rem]">
      <h1 className="font-heading text-4xl font-semibold leading-[1.1] tracking-tight text-balance md:text-5xl">
        Practise the conversations your work depends on.
      </h1>
      <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
        Rehearse stand-ups, code reviews, interviews and difficult talks with an AI partner, by text
        or by voice. Afterwards you see what you said, what got in the way, and a clearer way to say
        it.
      </p>

      <figure className="mt-12 rounded-2xl border bg-card px-6 py-7 md:px-8">
        <figcaption className="text-sm text-muted-foreground">
          What feedback looks like, from a stand-up update
        </figcaption>
        <blockquote className="mt-4 text-xl leading-relaxed">
          “<mark className="highlight-mark">So basically</mark>,{" "}
          <mark className="highlight-mark">um</mark>, the deploy is kind of blocked,{" "}
          <mark className="highlight-mark">I think</mark>?”
        </blockquote>
        <p className="mt-6 text-sm font-medium text-primary">A clearer way to say it</p>
        <p className="mt-1.5 text-xl leading-relaxed">
          “The deploy is blocked by a failing migration. I’ll have a fix out by 3 pm.”
        </p>
      </figure>

      <p className="mt-10 text-muted-foreground">
        Scenario practice opens in the next update. Until then, the sidebar shows whether the API,
        database and AI model are connected.
      </p>
    </div>
  );
}
