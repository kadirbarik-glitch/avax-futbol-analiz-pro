
    def test_past_ns_match_not_upcoming(self):
        client = app.test_client()

        matches = [
            sample_match("2026-11-11T10:00:00+03:00"),
            sample_match("2026-11-11T18:00:00+03:00"),
        ]

        with (
            patch(
                "v84_daily_app.today_turkey",
                return_value=date(2026, 11, 11),
            ),
            patch(
                "v84_daily_app.get_daily_fixtures",
                return_value={"matches": matches},
            ),
            patch(
                "v84_daily_app.render_template_string",
                return_value="Test page",
            ) as mocked_render,
            patch(
                "v84_daily_app.datetime",
                wraps=datetime,
            ) as mocked_datetime,
        ):
            mocked_datetime.now.return_value = self.now
            response = client.get("/")

        self.assertEqual(response.status_code, 200)

        context = mocked_render.call_args.kwargs
        self.assertEqual(context["stale"], [matches[0]])
        self.assertEqual(context["upcoming"], [matches[1]])
