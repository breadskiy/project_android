from pygments import highlight
from pygments.lexers import DartLexer
from pygments.formatters import ImageFormatter
from PIL import Image
import io

code = """Future<void> _login() async {
  if (!_formKey.currentState!.validate()) return;
  setState(() => _isLoading = true);
  try {
    await ApiService().login(
      _emailController.text.trim(),
      _passwordController.text,
    );
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const HomeShell()),
    );
  } catch (e) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Ошибка входа: $e')),
    );
  } finally {
    if (mounted) setState(() => _isLoading = false);
  }
}"""

formatter = ImageFormatter(
    style='monokai',
    line_numbers=False,
    font_name='Consolas',
    font_size=16,
)

img_bytes = highlight(code, DartLexer(), formatter)
img = Image.open(io.BytesIO(img_bytes))
img.save('scratch/test_code.png')
print(f"Saved test_code.png ({img.width}x{img.height})")
