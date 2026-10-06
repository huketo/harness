export default function SettingsPage() {
  return (
    <form>
      <label htmlFor="nickname">닉네임</label>
      <input id="nickname" name="nickname" />
      <button type="submit">Submit</button>
    </form>
  );
}
