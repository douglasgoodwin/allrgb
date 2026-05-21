// allcolors -- an image containing every RGB color exactly once.
// By fejesjoco (Joco), from the post "All RGB colors in one image"
// (2014-03-02), his answer to Code Golf Stack Exchange question #22144.
// Released by the author under the GPL.
// https://codegolf.stackexchange.com/questions/22144/images-with-all-colors

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Drawing;
using System.Drawing.Imaging;
using System.Diagnostics;
using System.IO;

class Program
{
    // algorithm settings, feel free to mess with it
    const bool AVERAGE = false;
    const int NUMCOLORS = 32;
    const int WIDTH = 256;
    const int HEIGHT = 128;
    const int STARTX = 128;
    const int STARTY = 64;

    // represent a coordinate
    struct XY
    {
        public int x, y;
        public XY(int x, int y)
        {
            this.x = x;
            this.y = y;
        }
        public override int GetHashCode()
        {
            return x ^ y;
        }
        public override bool Equals(object obj)
        {
            var that = (XY)obj;
            return this.x == that.x && this.y == that.y;
        }
    }

    // gets the difference between two colors
    static int coldiff(Color c1, Color c2)
    {
        var r = c1.R - c2.R;
        var g = c1.G - c2.G;
        var b = c1.B - c2.B;
        return r * r + g * g + b * b;
    }

    // gets the neighbors (3..8) of the given coordinate
    static List<XY> getneighbors(XY xy)
    {
        var ret = new List<XY>(8);
        for (var dy = -1; dy <= 1; dy++)
        {
            if (xy.y + dy == -1 || xy.y + dy == HEIGHT)
                continue;
            for (var dx = -1; dx <= 1; dx++)
            {
                if (xy.x + dx == -1 || xy.x + dx == WIDTH)
                    continue;
                ret.Add(new XY(xy.x + dx, xy.y + dy));
            }
        }
        return ret;
    }

    // calculates how well a color fits at the given coordinates
    static int calcdiff(Color[,] pixels, XY xy, Color c)
    {
        // get the diffs for each neighbor separately
        var diffs = new List<int>(8);
        foreach (var nxy in getneighbors(xy))
        {
            var nc = pixels[nxy.y, nxy.x];
            if (!nc.IsEmpty)
                diffs.Add(coldiff(nc, c));
        }

        // average or minimum selection
        if (AVERAGE)
            return (int)diffs.Average();
        else
            return diffs.Min();
    }

    static void Main(string[] args)
    {
        // create every color once and randomize the order
        var colors = new List<Color>();
        for (var r = 0; r < NUMCOLORS; r++)
            for (var g = 0; g < NUMCOLORS; g++)
                for (var b = 0; b < NUMCOLORS; b++)
                    colors.Add(Color.FromArgb(r * 255 / (NUMCOLORS - 1), g * 255 / (NUMCOLORS - 1), b * 255 / (NUMCOLORS - 1)));
        var rnd = new Random();
        colors.Sort(new Comparison<Color>((c1, c2) => rnd.Next(3) - 1));

        // temporary place where we work (faster than all that many GetPixel calls)
        var pixels = new Color[HEIGHT, WIDTH];
        Trace.Assert(pixels.Length == colors.Count);

        // constantly changing list of available coordinates (empty pixels which have non-empty neighbors)
        var available = new HashSet<XY>();

        // calculate the checkpoints in advance
        var checkpoints = Enumerable.Range(1, 10).ToDictionary(i => i * colors.Count / 10 - 1, i => i - 1);

        // loop through all colors that we want to place
        for (var i = 0; i < colors.Count; i++)
        {
            if (i % 256 == 0)
                Console.WriteLine("{0:P}, queue size {1}", (double)i / WIDTH / HEIGHT, available.Count);

            XY bestxy;
            if (available.Count == 0)
            {
                // use the starting point
                bestxy = new XY(STARTX, STARTY);
            }
            else
            {
                // find the best place from the list of available coordinates
                // uses parallel processing, this is the most expensive step
                bestxy = available.AsParallel().OrderBy(xy => calcdiff(pixels, xy, colors[i])).First();
            }

            // put the pixel where it belongs
            Trace.Assert(pixels[bestxy.y, bestxy.x].IsEmpty);
            pixels[bestxy.y, bestxy.x] = colors[i];

            // adjust the available list
            available.Remove(bestxy);
            foreach (var nxy in getneighbors(bestxy))
                if (pixels[nxy.y, nxy.x].IsEmpty)
                    available.Add(nxy);

            // save a checkpoint
            int chkidx;
            if (checkpoints.TryGetValue(i, out chkidx))
            {
                var img = new Bitmap(WIDTH, HEIGHT, PixelFormat.Format24bppRgb);
                for (var y = 0; y < HEIGHT; y++)
                {
                    for (var x = 0; x < WIDTH; x++)
                    {
                        img.SetPixel(x, y, pixels[y, x]);
                    }
                }
                img.Save("result" + chkidx + ".png");
            }
        }

        Trace.Assert(available.Count == 0);
    }
}